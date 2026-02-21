from __future__ import annotations

import json
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shannon.storage.postgres.client import pg_client
from shannon.storage.redis.client import redis_client

# 中文注释：流式事件管理器（参考原项目：Redis Stream + 本地广播 + 回放）


@dataclass
class Event:
    workflow_id: str
    type: str
    agent_id: str = ""
    message: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    seq: int = 0
    stream_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "type": self.type,
            "agent_id": self.agent_id,
            "message": self.message,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "seq": self.seq,
            "stream_id": self.stream_id,
        }


class StreamingManager:
    # 中文注释：函数 __init__ 的入口
    def __init__(self, capacity: Optional[int] = None) -> None:
        self.capacity = int(capacity or os.getenv("REDIS_STREAM_MAXLEN", "256") or 256)
        self._subscribers: dict[str, set[queue.Queue[Event]]] = {}
        self._memory_events: dict[str, list[Event]] = {}
        self._lock = threading.RLock()

    # 中文注释：函数 _stream_key 的入口
    def _stream_key(self, workflow_id: str) -> str:
        return f"shannon:workflow:events:{workflow_id}"

    # 中文注释：函数 _seq_key 的入口
    def _seq_key(self, workflow_id: str) -> str:
        return f"shannon:workflow:events:{workflow_id}:seq"

    # 中文注释：函数 subscribe 的入口
    def subscribe(self, workflow_id: str, buffer: int = 256) -> queue.Queue[Event]:
        ch: queue.Queue[Event] = queue.Queue(maxsize=max(1, buffer))
        with self._lock:
            self._subscribers.setdefault(workflow_id, set()).add(ch)
        return ch

    # 中文注释：函数 unsubscribe 的入口
    def unsubscribe(self, workflow_id: str, ch: queue.Queue[Event]) -> None:
        with self._lock:
            subs = self._subscribers.get(workflow_id)
            if not subs:
                return
            subs.discard(ch)
            if not subs:
                self._subscribers.pop(workflow_id, None)

    # 中文注释：函数 publish 的入口
    def publish(self, workflow_id: str, event: Event) -> Event:
        # 中文注释：统一补全 workflow_id 与序列号
        event.workflow_id = workflow_id
        event.timestamp = event.timestamp or time.time()

        seq = redis_client.incr(self._seq_key(workflow_id))
        event.seq = int(seq)

        fields = {
            "workflow_id": event.workflow_id,
            "type": event.type,
            "agent_id": event.agent_id,
            "message": event.message,
            "payload": event.payload,
            "ts_nano": int(event.timestamp * 1_000_000_000),
            "seq": event.seq,
        }

        stream_id = redis_client.xadd(self._stream_key(workflow_id), fields=fields, maxlen=self.capacity)
        event.stream_id = stream_id

        # 中文注释：设置 stream 与 seq key 过期，避免长期膨胀
        redis_client.expire(self._stream_key(workflow_id), 24 * 3600)
        redis_client.expire(self._seq_key(workflow_id), 48 * 3600)

        # 中文注释：事件落库（最佳努力，不阻塞）
        try:
            pg_client.append_event(
                thread_id=workflow_id,
                event_type=event.type,
                payload=event.payload,
                seq=event.seq,
                agent_id=event.agent_id,
                message=event.message,
                stream_id=event.stream_id,
            )
        except Exception:
            pass

        # 中文注释：保存内存 ring buffer（Redis 不可用时回放）
        with self._lock:
            bucket = self._memory_events.setdefault(workflow_id, [])
            bucket.append(event)
            if len(bucket) > self.capacity:
                self._memory_events[workflow_id] = bucket[-self.capacity :]

            # 中文注释：广播给本地订阅者，慢消费者丢弃最新事件避免阻塞
            for ch in list(self._subscribers.get(workflow_id, set())):
                try:
                    ch.put_nowait(event)
                except queue.Full:
                    # 中文注释：关键事件也不阻塞主链路
                    pass

        return event

    # 中文注释：函数 replay_since 的入口
    def replay_since(self, workflow_id: str, since_seq: int = 0, limit: int = 200) -> List[Event]:
        # 中文注释：优先读 Redis Stream，失败再回退内存
        rows = redis_client.xrange(self._stream_key(workflow_id), start="-", end="+", count=max(1, limit * 3))
        events: List[Event] = []

        if rows:
            for row in rows:
                fields = row.get("fields", {}) if isinstance(row, dict) else {}
                seq = int(fields.get("seq") or 0)
                if seq <= int(since_seq):
                    continue

                payload_raw = fields.get("payload")
                payload: Dict[str, Any] = {}
                if isinstance(payload_raw, str) and payload_raw:
                    try:
                        parsed = json.loads(payload_raw)
                        if isinstance(parsed, dict):
                            payload = parsed
                    except Exception:
                        payload = {}
                elif isinstance(payload_raw, dict):
                    payload = payload_raw

                ts_nano = int(fields.get("ts_nano") or 0)
                timestamp = ts_nano / 1_000_000_000 if ts_nano > 0 else time.time()

                events.append(
                    Event(
                        workflow_id=workflow_id,
                        type=str(fields.get("type") or ""),
                        agent_id=str(fields.get("agent_id") or ""),
                        message=str(fields.get("message") or ""),
                        payload=payload,
                        timestamp=timestamp,
                        seq=seq,
                        stream_id=str(row.get("id") or ""),
                    )
                )

            if events:
                return events[-max(1, limit) :]

        with self._lock:
            bucket = list(self._memory_events.get(workflow_id, []))
        filtered = [event for event in bucket if int(event.seq) > int(since_seq)]
        return filtered[-max(1, limit) :]

    # 中文注释：函数 replay_from_stream_id 的入口
    def replay_from_stream_id(self, workflow_id: str, stream_id: str, limit: int = 200) -> List[Event]:
        rows = redis_client.xrange(self._stream_key(workflow_id), start=stream_id, end="+", count=max(1, limit))
        events: List[Event] = []
        for row in rows:
            sid = str(row.get("id") or "")
            if sid <= stream_id:
                continue
            fields = row.get("fields", {}) if isinstance(row, dict) else {}
            payload_raw = fields.get("payload")
            payload: Dict[str, Any] = {}
            if isinstance(payload_raw, str) and payload_raw:
                try:
                    parsed = json.loads(payload_raw)
                    if isinstance(parsed, dict):
                        payload = parsed
                except Exception:
                    payload = {}
            ts_nano = int(fields.get("ts_nano") or 0)
            timestamp = ts_nano / 1_000_000_000 if ts_nano > 0 else time.time()
            events.append(
                Event(
                    workflow_id=workflow_id,
                    type=str(fields.get("type") or ""),
                    agent_id=str(fields.get("agent_id") or ""),
                    message=str(fields.get("message") or ""),
                    payload=payload,
                    timestamp=timestamp,
                    seq=int(fields.get("seq") or 0),
                    stream_id=sid,
                )
            )
        return events[-max(1, limit) :]

    # 中文注释：函数 get_last_stream_id 的入口
    def get_last_stream_id(self, workflow_id: str) -> str:
        rows = redis_client.xrevrange(self._stream_key(workflow_id), count=1)
        if rows:
            return str(rows[0].get("id") or "")
        return ""


# 中文注释：单例 Streaming 管理器
streaming_manager = StreamingManager()
