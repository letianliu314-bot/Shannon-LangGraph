from __future__ import annotations

from shannon.storage.postgres.client import pg_client

# 中文注释：任务执行日志存储


class TaskLogger:
    # 中文注释：函数 log 的入口
    def log(self, thread_id: str, task_id: str, status: str) -> None:
        # 中文注释：写入任务日志到 PostgreSQL（不可用时自动降级到内存）
        pg_client.log_task(thread_id=thread_id, task_id=task_id, status=status)
