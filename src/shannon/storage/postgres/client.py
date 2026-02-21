from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from shannon.storage.postgres.schema import BOOTSTRAP_SQL

# 中文注释：PostgreSQL 客户端（优先真实连接，失败回退内存）


class InMemoryPostgres:
    # 中文注释：内存回退存储，确保外部依赖不可用时主流程不崩溃
    def __init__(self) -> None:
        self.checkpoints: dict[str, list[str]] = {}
        self.states_latest: dict[str, dict[str, Any]] = {}
        self.state_snapshots: dict[str, list[dict[str, Any]]] = {}
        self.event_logs: dict[str, list[dict[str, Any]]] = {}
        self.task_logs: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def insert_checkpoint(self, thread_id: str, checkpoint_id: str) -> None:
        with self._lock:
            self.checkpoints.setdefault(thread_id, []).append(checkpoint_id)

    def latest_checkpoint(self, thread_id: str) -> str | None:
        with self._lock:
            items = self.checkpoints.get(thread_id)
            return items[-1] if items else None

    def list_checkpoints(self, thread_id: str, limit: int = 100) -> list[str]:
        with self._lock:
            items = list(self.checkpoints.get(thread_id, []))
            return items[-max(1, limit) :]

    def save_thread_state(self, thread_id: str, state: Dict[str, Any], status: str) -> None:
        payload = {
            "thread_id": thread_id,
            "status": status,
            "state_json": state,
        }
        with self._lock:
            self.states_latest[thread_id] = payload
            self.state_snapshots.setdefault(thread_id, []).append(payload)

    def get_thread_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.states_latest.get(thread_id)
            return dict(row) if row else None

    def list_thread_state_snapshots(self, thread_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        with self._lock:
            items = list(self.state_snapshots.get(thread_id, []))
            return items[-max(1, limit) :]

    def append_event(
        self,
        thread_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        seq: Optional[int] = None,
        agent_id: Optional[str] = None,
        message: Optional[str] = None,
        stream_id: Optional[str] = None,
    ) -> None:
        event = {
            "thread_id": thread_id,
            "event_type": event_type,
            "agent_id": agent_id,
            "message": message,
            "payload": payload or {},
            "seq": seq,
            "stream_id": stream_id,
        }
        with self._lock:
            self.event_logs.setdefault(thread_id, []).append(event)

    def list_events(self, thread_id: str, since_seq: int = 0, limit: int = 200) -> list[Dict[str, Any]]:
        with self._lock:
            events = list(self.event_logs.get(thread_id, []))
        filtered = []
        for event in events:
            seq = int(event.get("seq") or 0)
            if seq > int(since_seq):
                filtered.append(event)
        return filtered[-max(1, limit) :]

    def log_task(self, thread_id: str, task_id: str, status: str) -> None:
        with self._lock:
            self.task_logs.append({"thread_id": thread_id, "task_id": task_id, "status": status})


class PostgresClient:
    # 中文注释：函数 __init__ 的入口
    def __init__(self) -> None:
        self.dsn = os.getenv("POSTGRES_DSN", "").strip()
        self.migrations_path = os.getenv("POSTGRES_MIGRATIONS_PATH", "migrations/postgres")
        self._memory = InMemoryPostgres()
        self._lock = threading.RLock()
        self._driver = None
        self._available = False
        self._init_driver()

    # 中文注释：函数 _init_driver 的入口
    def _init_driver(self) -> None:
        # 中文注释：无 DSN 时直接进入内存模式
        if not self.dsn:
            self._driver = None
            self._available = False
            return

        try:
            import psycopg  # type: ignore

            self._driver = psycopg
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            self._available = True
        except Exception:
            # 中文注释：连接失败时自动降级，不影响主流程
            self._driver = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # 中文注释：函数 _execute 的入口
    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if not self.available or self._driver is None:
            return
        with self._driver.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    # 中文注释：函数 _execute_script 的入口
    def _execute_script(self, sql_text: str) -> None:
        # 中文注释：优先按整段脚本执行（兼容函数/触发器定义）；失败时再降级分号拆分
        if not sql_text.strip():
            return
        if self.available and self._driver is not None:
            try:
                with self._driver.connect(self.dsn) as conn:
                    with conn.cursor() as cur:
                        # 中文注释：prepare=False 允许一次执行多条语句
                        cur.execute(sql_text, prepare=False)
                    conn.commit()
                return
            except Exception:
                # 中文注释：保底降级为逐语句执行，确保简单 SQL 仍可完成迁移
                pass

        fragments = sql_text.split(";")
        for fragment in fragments:
            statement = fragment.strip()
            if statement:
                self._execute(statement + ";")

    # 中文注释：函数 _fetchone 的入口
    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[tuple[Any, ...]]:
        if not self.available or self._driver is None:
            return None
        with self._driver.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return row

    # 中文注释：函数 _fetchall 的入口
    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        if not self.available or self._driver is None:
            return []
        with self._driver.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return rows

    # 中文注释：函数 run_migrations 的入口
    def run_migrations(self) -> None:
        # 中文注释：优先读取外部 migrations 目录，不存在则执行内置 bootstrap SQL
        if not self.available:
            return

        migration_files: list[Path] = []
        root = Path(self.migrations_path)
        if root.exists() and root.is_dir():
            migration_files = sorted(root.glob("*.sql"))

        if migration_files:
            for file_path in migration_files:
                sql_text = file_path.read_text(encoding="utf-8")
                if not sql_text.strip():
                    continue
                self._execute_script(sql_text)
            return

        for statement in BOOTSTRAP_SQL:
            self._execute_script(statement)

    # 中文注释：函数 insert_checkpoint 的入口（兼容旧接口）
    def insert_checkpoint(self, thread_id: str, checkpoint_id: str) -> None:
        if not self.available:
            self._memory.insert_checkpoint(thread_id, checkpoint_id)
            return

        self._execute(
            "INSERT INTO state_history (thread_id, checkpoint_id) VALUES (%s, %s)",
            (thread_id, checkpoint_id),
        )

    # 中文注释：函数 latest_checkpoint 的入口（兼容旧接口）
    def latest_checkpoint(self, thread_id: str) -> str | None:
        if not self.available:
            return self._memory.latest_checkpoint(thread_id)

        row = self._fetchone(
            "SELECT checkpoint_id FROM state_history WHERE thread_id = %s ORDER BY created_at DESC LIMIT 1",
            (thread_id,),
        )
        return str(row[0]) if row else None

    # 中文注释：函数 list_checkpoints 的入口
    def list_checkpoints(self, thread_id: str, limit: int = 100) -> list[str]:
        if not self.available:
            return self._memory.list_checkpoints(thread_id, limit=limit)

        rows = self._fetchall(
            "SELECT checkpoint_id FROM state_history WHERE thread_id = %s ORDER BY created_at DESC LIMIT %s",
            (thread_id, max(1, int(limit))),
        )
        return [str(row[0]) for row in rows]

    # 中文注释：函数 save_thread_state 的入口
    def save_thread_state(self, thread_id: str, state: Dict[str, Any], status: str = "updated") -> None:
        if not self.available:
            self._memory.save_thread_state(thread_id, state, status)
            return

        state_json = json.dumps(state, ensure_ascii=False)
        self._execute(
            """
            INSERT INTO run_states_latest (thread_id, status, state_json, updated_at)
            VALUES (%s, %s, %s::jsonb, NOW())
            ON CONFLICT (thread_id) DO UPDATE SET
                status = EXCLUDED.status,
                state_json = EXCLUDED.state_json,
                updated_at = NOW()
            """,
            (thread_id, status, state_json),
        )
        self._execute(
            "INSERT INTO run_state_snapshots (thread_id, status, state_json) VALUES (%s, %s, %s::jsonb)",
            (thread_id, status, state_json),
        )

    # 中文注释：函数 get_thread_state 的入口
    def get_thread_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        if not self.available:
            return self._memory.get_thread_state(thread_id)

        row = self._fetchone(
            "SELECT status, state_json::text, updated_at FROM run_states_latest WHERE thread_id = %s",
            (thread_id,),
        )
        if not row:
            return None
        return {
            "thread_id": thread_id,
            "status": row[0],
            "state_json": json.loads(str(row[1])) if row[1] else {},
            "updated_at": row[2],
        }

    # 中文注释：函数 list_thread_state_snapshots 的入口
    def list_thread_state_snapshots(self, thread_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        if not self.available:
            return self._memory.list_thread_state_snapshots(thread_id, limit=limit)

        rows = self._fetchall(
            """
            SELECT status, state_json::text, created_at
            FROM run_state_snapshots
            WHERE thread_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (thread_id, max(1, int(limit))),
        )
        result: list[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "thread_id": thread_id,
                    "status": row[0],
                    "state_json": json.loads(str(row[1])) if row[1] else {},
                    "created_at": row[2],
                }
            )
        return result

    # 中文注释：函数 append_event 的入口
    def append_event(
        self,
        thread_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        seq: Optional[int] = None,
        agent_id: Optional[str] = None,
        message: Optional[str] = None,
        stream_id: Optional[str] = None,
    ) -> None:
        payload_obj = payload or {}
        if not self.available:
            self._memory.append_event(
                thread_id=thread_id,
                event_type=event_type,
                payload=payload_obj,
                seq=seq,
                agent_id=agent_id,
                message=message,
                stream_id=stream_id,
            )
            return

        self._execute(
            """
            INSERT INTO event_logs (thread_id, event_type, agent_id, message, payload, seq, stream_id)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                thread_id,
                event_type,
                agent_id,
                message,
                json.dumps(payload_obj, ensure_ascii=False),
                seq,
                stream_id,
            ),
        )

    # 中文注释：函数 list_events 的入口
    def list_events(self, thread_id: str, since_seq: int = 0, limit: int = 200) -> list[Dict[str, Any]]:
        if not self.available:
            return self._memory.list_events(thread_id=thread_id, since_seq=since_seq, limit=limit)

        rows = self._fetchall(
            """
            SELECT event_type, agent_id, message, payload::text, seq, stream_id, created_at
            FROM event_logs
            WHERE thread_id = %s AND COALESCE(seq, 0) > %s
            ORDER BY seq ASC NULLS LAST, created_at ASC
            LIMIT %s
            """,
            (thread_id, int(since_seq), max(1, int(limit))),
        )
        result: list[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "thread_id": thread_id,
                    "event_type": row[0],
                    "agent_id": row[1],
                    "message": row[2],
                    "payload": json.loads(str(row[3])) if row[3] else {},
                    "seq": row[4],
                    "stream_id": row[5],
                    "created_at": row[6],
                }
            )
        return result

    # 中文注释：函数 log_task 的入口
    def log_task(self, thread_id: str, task_id: str, status: str) -> None:
        if not self.available:
            self._memory.log_task(thread_id=thread_id, task_id=task_id, status=status)
            return

        self._execute(
            "INSERT INTO task_log (thread_id, task_id, status) VALUES (%s, %s, %s)",
            (thread_id, task_id, status),
        )


# 中文注释：单例 PG 客户端
pg_client = PostgresClient()
