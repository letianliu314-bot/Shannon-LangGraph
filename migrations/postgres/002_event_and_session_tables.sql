-- 中文注释：事件流与会话归档（参考 Shannon-1 event/session 语义）

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

CREATE INDEX IF NOT EXISTS idx_event_logs_thread_id_seq
ON event_logs(thread_id, seq DESC);

CREATE INDEX IF NOT EXISTS idx_event_logs_thread_id_created_at
ON event_logs(thread_id, created_at DESC);

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

CREATE INDEX IF NOT EXISTS idx_session_archives_session_id
ON session_archives(session_id);

CREATE INDEX IF NOT EXISTS idx_session_archives_snapshot_taken_at
ON session_archives(snapshot_taken_at DESC);
