from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shannon.storage.redis.client import redis_client

# 中文注释：Session 管理器（参考原项目 Go 逻辑：TTL + history 限制 + 本地 LRU 热缓存）


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionData:
    id: str
    user_id: str
    tenant_id: str
    created_at: float
    updated_at: float
    expires_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    history: List[SessionMessage] = field(default_factory=list)

    def is_expired(self) -> bool:
        return time.time() > float(self.expires_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
            "context": self.context,
            "history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "metadata": msg.metadata,
                }
                for msg in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        history_items = data.get("history") if isinstance(data.get("history"), list) else []
        history: List[SessionMessage] = []
        for item in history_items:
            if not isinstance(item, dict):
                continue
            history.append(
                SessionMessage(
                    role=str(item.get("role") or "user"),
                    content=str(item.get("content") or ""),
                    timestamp=float(item.get("timestamp") or time.time()),
                    metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                )
            )

        return cls(
            id=str(data.get("id") or ""),
            user_id=str(data.get("user_id") or "anonymous"),
            tenant_id=str(data.get("tenant_id") or ""),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            expires_at=float(data.get("expires_at") or (time.time() + 86400)),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            context=data.get("context") if isinstance(data.get("context"), dict) else {},
            history=history,
        )


class SessionManager:
    # 中文注释：函数 __init__ 的入口
    def __init__(
        self,
        ttl_seconds: Optional[int] = None,
        max_history: Optional[int] = None,
        cache_size: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> None:
        self.ttl_seconds = int(ttl_seconds or os.getenv("SESSION_TTL_SECONDS", "2592000") or 2592000)
        self.max_history = int(max_history or os.getenv("SESSION_MAX_HISTORY", "500") or 500)
        self.cache_size = int(cache_size or os.getenv("SESSION_LOCAL_CACHE_SIZE", "10000") or 10000)
        self.max_rounds = int(max_rounds or os.getenv("SESSION_SLIDING_WINDOW_ROUNDS", "5") or 5)

        self._cache: OrderedDict[str, SessionData] = OrderedDict()
        self._lock = threading.RLock()

    # 中文注释：函数 _session_key 的入口
    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    # 中文注释：函数 _save_to_redis 的入口
    def _save_to_redis(self, session: SessionData) -> None:
        key = self._session_key(session.id)
        ttl = max(1, int(session.expires_at - time.time()))
        redis_client.set(key, json.dumps(session.to_dict(), ensure_ascii=False), ex=ttl)

    def _touch_session_ttl(self, session: SessionData) -> None:
        # 中文注释：滑动 TTL：每次有效写入都刷新到固定会话寿命
        session.expires_at = time.time() + self.ttl_seconds

    def _trim_history_by_rounds(self, history: List[SessionMessage]) -> List[SessionMessage]:
        # 中文注释：仅保留最近 N 个用户轮次（默认 5 轮问答）
        if self.max_rounds <= 0:
            return history
        user_indexes = [idx for idx, msg in enumerate(history) if str(msg.role).lower() == "user"]
        if len(user_indexes) <= self.max_rounds:
            return history
        start_idx = user_indexes[-self.max_rounds]
        return history[start_idx:]

    # 中文注释：函数 _cache_set 的入口
    def _cache_set(self, session: SessionData) -> None:
        with self._lock:
            self._cache[session.id] = session
            self._cache.move_to_end(session.id)
            if len(self._cache) > self.cache_size:
                # 中文注释：按 LRU 淘汰最旧会话（一次淘汰一半，降低抖动）
                evict_count = max(1, self.cache_size // 2)
                for _ in range(min(evict_count, len(self._cache))):
                    self._cache.popitem(last=False)

    # 中文注释：函数 create_session 的入口
    def create_session(
        self,
        user_id: str = "anonymous",
        tenant_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> SessionData:
        now = time.time()
        sid = session_id or str(uuid.uuid4())
        existing = self.get_session(sid)
        if existing is not None and existing.user_id == user_id:
            return existing

        session = SessionData(
            id=sid,
            user_id=user_id,
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
            expires_at=now + self.ttl_seconds,
            metadata=metadata or {},
            context={},
            history=[],
        )
        self._save_to_redis(session)
        self._cache_set(session)
        return session

    # 中文注释：函数 get_session 的入口
    def get_session(self, session_id: str) -> Optional[SessionData]:
        with self._lock:
            cached = self._cache.get(session_id)
            if cached is not None:
                if cached.is_expired():
                    self._cache.pop(session_id, None)
                    redis_client.delete(self._session_key(session_id))
                    return None
                self._cache.move_to_end(session_id)
                return cached

        key = self._session_key(session_id)
        raw = redis_client.get(key)
        if not raw:
            return None

        try:
            payload = json.loads(raw)
            session = SessionData.from_dict(payload if isinstance(payload, dict) else {})
        except Exception:
            return None

        if session.is_expired():
            redis_client.delete(key)
            return None

        self._cache_set(session)
        return session

    # 中文注释：函数 update_session 的入口
    def update_session(self, session: SessionData, refresh_ttl: bool = True) -> None:
        session.updated_at = time.time()
        if refresh_ttl:
            self._touch_session_ttl(session)
        self._save_to_redis(session)
        self._cache_set(session)

    # 中文注释：函数 delete_session 的入口
    def delete_session(self, session_id: str) -> None:
        redis_client.delete(self._session_key(session_id))
        with self._lock:
            self._cache.pop(session_id, None)

    # 中文注释：函数 extend_session 的入口
    def extend_session(self, session_id: str, duration_seconds: int) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        session.expires_at = time.time() + max(1, int(duration_seconds))
        self.update_session(session, refresh_ttl=False)
        return True

    # 中文注释：函数 add_message 的入口
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False

        session.history.append(
            SessionMessage(
                role=role,
                content=content,
                timestamp=time.time(),
                metadata=metadata or {},
            )
        )
        session.history = self._trim_history_by_rounds(session.history)
        if len(session.history) > self.max_history:
            session.history = session.history[-self.max_history :]
        self.update_session(session)
        return True

    # 中文注释：函数 update_context 的入口
    def update_context(self, session_id: str, key: str, value: Any) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        session.context[key] = value
        self.update_session(session)
        return True

    # 中文注释：函数 list_user_sessions 的入口
    def list_user_sessions(self, user_id: str) -> List[SessionData]:
        keys = redis_client.keys("session:*")
        result: List[SessionData] = []
        for key in keys:
            raw = redis_client.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            session = SessionData.from_dict(payload)
            if session.user_id == user_id and not session.is_expired():
                result.append(session)
        return result

    # 中文注释：函数 cleanup_expired 的入口
    def cleanup_expired(self) -> int:
        keys = redis_client.keys("session:*")
        removed = 0
        for key in keys:
            raw = redis_client.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
                session = SessionData.from_dict(payload if isinstance(payload, dict) else {})
            except Exception:
                continue
            if session.is_expired():
                redis_client.delete(key)
                removed += 1
                with self._lock:
                    self._cache.pop(session.id, None)
        return removed


# 中文注释：单例 Session 管理器
session_manager = SessionManager()
