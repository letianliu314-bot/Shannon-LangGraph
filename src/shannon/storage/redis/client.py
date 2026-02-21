from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

# 中文注释：Redis 客户端（优先真实连接，失败回退内存）


class InMemoryRedis:
    # 中文注释：内存回退实现，支持 KV/TTL/Counter/Stream
    def __init__(self) -> None:
        self._kv: dict[str, tuple[str, Optional[float]]] = {}
        self._hash: dict[str, dict[str, str]] = {}
        self._stream: dict[str, list[dict[str, Any]]] = {}
        self._counter: dict[str, int] = {}
        self._lock = threading.RLock()

    def _cleanup_if_expired(self, key: str) -> None:
        item = self._kv.get(key)
        if item is None:
            return
        _, expire_at = item
        if expire_at is not None and time.time() > expire_at:
            self._kv.pop(key, None)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        with self._lock:
            expire_at = time.time() + ex if ex and ex > 0 else None
            self._kv[key] = (value, expire_at)

    def get(self, key: str) -> str | None:
        with self._lock:
            self._cleanup_if_expired(key)
            item = self._kv.get(key)
            return item[0] if item else None

    def delete(self, key: str) -> int:
        with self._lock:
            existed = 1 if key in self._kv else 0
            self._kv.pop(key, None)
            self._hash.pop(key, None)
            self._stream.pop(key, None)
            return existed

    def expire(self, key: str, ex: int) -> bool:
        with self._lock:
            item = self._kv.get(key)
            if item is None:
                return False
            self._kv[key] = (item[0], time.time() + max(1, ex))
            return True

    def incr(self, key: str) -> int:
        with self._lock:
            value = int(self._counter.get(key, 0)) + 1
            self._counter[key] = value
            return value

    def keys(self, pattern: str) -> list[str]:
        # 中文注释：仅支持简单前缀匹配（pattern 以 * 结尾）
        with self._lock:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k for k in self._kv.keys() if k.startswith(prefix)]
            return [k for k in self._kv.keys() if k == pattern]

    def hset(self, key: str, mapping: Dict[str, str]) -> None:
        with self._lock:
            bucket = self._hash.setdefault(key, {})
            for k, v in mapping.items():
                bucket[str(k)] = str(v)

    def hgetall(self, key: str) -> dict[str, str]:
        with self._lock:
            return dict(self._hash.get(key, {}))

    def xadd(self, key: str, fields: Dict[str, Any], maxlen: Optional[int] = None) -> str:
        with self._lock:
            now_ms = int(time.time() * 1000)
            seq = self.incr(f"{key}:stream_seq")
            stream_id = f"{now_ms}-{seq}"
            entries = self._stream.setdefault(key, [])
            entries.append({"id": stream_id, "fields": dict(fields)})
            if maxlen and maxlen > 0 and len(entries) > maxlen:
                self._stream[key] = entries[-maxlen:]
            return stream_id

    def xrange(self, key: str, start: str = "-", end: str = "+", count: Optional[int] = None) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(self._stream.get(key, []))

        def in_range(entry_id: str) -> bool:
            if start not in {"-", ""} and entry_id <= start:
                return False
            if end not in {"+", ""} and entry_id > end:
                return False
            return True

        filtered = [entry for entry in entries if in_range(str(entry.get("id", "")))]
        if count and count > 0:
            filtered = filtered[:count]
        return filtered

    def xrevrange(self, key: str, start: str = "+", end: str = "-", count: Optional[int] = None) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(reversed(self._stream.get(key, [])))
        if count and count > 0:
            entries = entries[:count]
        return entries


class RedisClient:
    # 中文注释：函数 __init__ 的入口
    def __init__(self) -> None:
        self.url = os.getenv("REDIS_URL", "").strip()
        self.stream_maxlen = int(os.getenv("REDIS_STREAM_MAXLEN", "256") or 256)
        self._memory = InMemoryRedis()
        self._client = None
        self._available = False
        self._init_driver()

    # 中文注释：函数 _init_driver 的入口
    def _init_driver(self) -> None:
        if not self.url:
            self._client = None
            self._available = False
            return

        try:
            import redis as redis_driver  # type: ignore

            client = redis_driver.Redis.from_url(
                self.url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
            )
            client.ping()
            self._client = client
            self._available = True
        except Exception:
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # 中文注释：函数 set 的入口
    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        if self.available and self._client is not None:
            self._client.set(key, value, ex=ex)
            return
        self._memory.set(key, value, ex=ex)

    # 中文注释：函数 get 的入口
    def get(self, key: str) -> str | None:
        if self.available and self._client is not None:
            data = self._client.get(key)
            return str(data) if data is not None else None
        return self._memory.get(key)

    # 中文注释：函数 delete 的入口
    def delete(self, key: str) -> int:
        if self.available and self._client is not None:
            return int(self._client.delete(key))
        return self._memory.delete(key)

    # 中文注释：函数 expire 的入口
    def expire(self, key: str, ex: int) -> bool:
        if self.available and self._client is not None:
            return bool(self._client.expire(key, ex))
        return self._memory.expire(key, ex)

    # 中文注释：函数 incr 的入口
    def incr(self, key: str) -> int:
        if self.available and self._client is not None:
            return int(self._client.incr(key))
        return self._memory.incr(key)

    # 中文注释：函数 keys 的入口
    def keys(self, pattern: str) -> list[str]:
        if self.available and self._client is not None:
            return [str(item) for item in self._client.keys(pattern)]
        return self._memory.keys(pattern)

    # 中文注释：函数 hset 的入口
    def hset(self, key: str, mapping: Dict[str, str]) -> None:
        if self.available and self._client is not None:
            self._client.hset(key, mapping=mapping)
            return
        self._memory.hset(key, mapping=mapping)

    # 中文注释：函数 hgetall 的入口
    def hgetall(self, key: str) -> dict[str, str]:
        if self.available and self._client is not None:
            return {str(k): str(v) for k, v in self._client.hgetall(key).items()}
        return self._memory.hgetall(key)

    # 中文注释：函数 xadd 的入口
    def xadd(self, key: str, fields: Dict[str, Any], maxlen: Optional[int] = None) -> str:
        effective_maxlen = maxlen if maxlen is not None else self.stream_maxlen
        if self.available and self._client is not None:
            payload = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)) for k, v in fields.items()}
            stream_id = self._client.xadd(key, fields=payload, maxlen=effective_maxlen, approximate=True)
            return str(stream_id)
        return self._memory.xadd(key, fields=fields, maxlen=effective_maxlen)

    # 中文注释：函数 xrange 的入口
    def xrange(self, key: str, start: str = "-", end: str = "+", count: Optional[int] = None) -> list[dict[str, Any]]:
        if self.available and self._client is not None:
            rows = self._client.xrange(key, min=start, max=end, count=count)
            result: list[dict[str, Any]] = []
            for stream_id, fields in rows:
                result.append({"id": str(stream_id), "fields": {str(k): v for k, v in fields.items()}})
            return result
        return self._memory.xrange(key, start=start, end=end, count=count)

    # 中文注释：函数 xrevrange 的入口
    def xrevrange(self, key: str, start: str = "+", end: str = "-", count: Optional[int] = None) -> list[dict[str, Any]]:
        if self.available and self._client is not None:
            rows = self._client.xrevrange(key, max=start, min=end, count=count)
            result: list[dict[str, Any]] = []
            for stream_id, fields in rows:
                result.append({"id": str(stream_id), "fields": {str(k): v for k, v in fields.items()}})
            return result
        return self._memory.xrevrange(key, start=start, end=end, count=count)

    # 中文注释：函数 close 的入口
    def close(self) -> None:
        if self.available and self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass


# 中文注释：单例客户端
redis_client = RedisClient()
