-- 中文注释：初始化 PG 表
CREATE TABLE IF NOT EXISTS state_history (
  id SERIAL PRIMARY KEY,
  thread_id TEXT NOT NULL,
  checkpoint_id TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_log (
  id SERIAL PRIMARY KEY,
  thread_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  status TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
