-- 中文注释：任务执行日志（兼容当前 Python TaskLogger）

CREATE TABLE IF NOT EXISTS task_log (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_log_thread_id_created_at
ON task_log(thread_id, created_at DESC);
