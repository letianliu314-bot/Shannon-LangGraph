from __future__ import annotations

# 中文注释：PostgreSQL 启动表结构（最小可用，参考 Shannon-1 migrations 抽取）

BOOTSTRAP_SQL: list[str] = [
    # 中文注释：会话归档表（长期保存 Redis 会话快照）
    """
    CREATE TABLE IF NOT EXISTS session_archives (
        id BIGSERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        user_id TEXT,
        snapshot_data JSONB DEFAULT '{}'::jsonb,
        message_count INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        total_cost_usd DOUBLE PRECISION DEFAULT 0,
        session_started_at TIMESTAMPTZ,
        snapshot_taken_at TIMESTAMPTZ DEFAULT NOW(),
        ttl_expires_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_session_archives_session_id ON session_archives(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_session_archives_snapshot_taken_at ON session_archives(snapshot_taken_at DESC);",
    # 中文注释：checkpoint 历史表
    """
    CREATE TABLE IF NOT EXISTS state_history (
        id BIGSERIAL PRIMARY KEY,
        thread_id TEXT NOT NULL,
        checkpoint_id TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_state_history_thread_id_created_at ON state_history(thread_id, created_at DESC);",
    # 中文注释：线程状态最新表（用于快速恢复）
    """
    CREATE TABLE IF NOT EXISTS run_states_latest (
        thread_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        state_json JSONB NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    # 中文注释：线程状态快照历史表
    """
    CREATE TABLE IF NOT EXISTS run_state_snapshots (
        id BIGSERIAL PRIMARY KEY,
        thread_id TEXT NOT NULL,
        status TEXT NOT NULL,
        state_json JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_run_state_snapshots_thread_id_created_at ON run_state_snapshots(thread_id, created_at DESC);",
    # 中文注释：流式事件日志（用于回放与审计）
    """
    CREATE TABLE IF NOT EXISTS event_logs (
        id BIGSERIAL PRIMARY KEY,
        thread_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        agent_id TEXT,
        message TEXT,
        payload JSONB DEFAULT '{}'::jsonb,
        seq BIGINT,
        stream_id TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_logs_thread_id_seq ON event_logs(thread_id, seq DESC);",
    "CREATE INDEX IF NOT EXISTS idx_event_logs_thread_id_created_at ON event_logs(thread_id, created_at DESC);",
    # 中文注释：任务日志表（兼容旧模块）
    """
    CREATE TABLE IF NOT EXISTS task_log (
        id BIGSERIAL PRIMARY KEY,
        thread_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        status TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_task_log_thread_id_created_at ON task_log(thread_id, created_at DESC);",
]
