-- 中文注释：基础表（参考 Shannon-1 001/002，按当前 Python orchestrator 最小可用裁剪）

CREATE TABLE IF NOT EXISTS state_history (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_state_history_thread_id_created_at
ON state_history(thread_id, created_at DESC);

CREATE TABLE IF NOT EXISTS run_states_latest (
    thread_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    state_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_state_snapshots (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    status TEXT NOT NULL,
    state_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_state_snapshots_thread_id_created_at
ON run_state_snapshots(thread_id, created_at DESC);
