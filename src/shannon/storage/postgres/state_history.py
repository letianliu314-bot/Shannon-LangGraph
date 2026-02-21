from __future__ import annotations

from shannon.storage.postgres.client import pg_client

# 中文注释：状态历史存储


class StateHistoryStore:
    # 中文注释：函数 record_checkpoint 的入口
    def record_checkpoint(self, thread_id: str, checkpoint_id: str) -> None:
        # 中文注释：写入 checkpoint 历史
        pg_client.insert_checkpoint(thread_id, checkpoint_id)

    # 中文注释：函数 latest_checkpoint 的入口
    def latest_checkpoint(self, thread_id: str) -> str | None:
        # 中文注释：读取最新 checkpoint
        return pg_client.latest_checkpoint(thread_id)

    # 中文注释：函数 list_checkpoints 的入口
    def list_checkpoints(self, thread_id: str, limit: int = 100) -> list[str]:
        # 中文注释：读取 checkpoint 列表
        return pg_client.list_checkpoints(thread_id, limit=limit)
