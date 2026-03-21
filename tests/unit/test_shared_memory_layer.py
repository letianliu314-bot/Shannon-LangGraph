from __future__ import annotations

from pathlib import Path

from shannon.storage.memory_layer.store import SharedMemoryStore

# 中文注释：共享记忆层单测
# 目标：验证写入检索契约、路径安全与质量优先+时间衰减排序策略


def test_shared_memory_contract(tmp_path: Path):
    # 中文注释：基础契约测试，确认 upsert 与 search 的核心字段一致
    store = SharedMemoryStore(root_dir=str(tmp_path / "reports"))
    store.ensure_run_manifest("run-1")

    record = store.upsert_task_record(
        run_id="run-1",
        task_id="task-1",
        content="test content",
        stage="phase-1",
        capability="infra",
        agent="infra-agent",
        metadata={"quality_score": 0.9, "decay_score": 0.8},
    )
    assert record["run_id"] == "run-1"
    assert record["task_id"] == "task-1"

    hits = store.search_records(run_id="run-1", task_id="task-1", stage="phase-1", capability="infra", limit=5)
    assert len(hits) == 1
    assert hits[0]["content"] == "test content"


def test_shared_memory_blocks_path_traversal(tmp_path: Path):
    # 中文注释：安全测试，禁止通过 ../ 进行目录穿越写入
    store = SharedMemoryStore(root_dir=str(tmp_path / "reports"))
    store.ensure_run_manifest("run-1")

    blocked = False
    try:
        store.write_run_file("run-1", "../run-2/hack.md", "bad")
    except ValueError:
        blocked = True

    assert blocked


def test_shared_memory_quality_first_with_time_decay(tmp_path: Path):
    # 中文注释：排序测试，验证“质量优先 + 时间衰减”联合评分逻辑
    store = SharedMemoryStore(root_dir=str(tmp_path / "reports"))
    store.ensure_run_manifest("run-rank")

    # 中文注释：即使较旧，质量显著更高时应优先排序
    store.upsert_task_record(
        run_id="run-rank",
        task_id="task-high-quality",
        content="high quality",
        stage="phase-5",
        capability="ranking",
        metadata={"quality_score": 0.99, "decay_score": 0.3},
    )
    store.upsert_task_record(
        run_id="run-rank",
        task_id="task-low-quality",
        content="low quality",
        stage="phase-5",
        capability="ranking",
        metadata={"quality_score": 0.2, "decay_score": 1.0},
    )

    hits = store.search_records(run_id="run-rank", capability="ranking", limit=5)
    assert len(hits) == 2
    assert hits[0]["task_id"] == "task-high-quality"
    assert "quality_score" in hits[0]
    assert "decay_score" in hits[0]
    assert "final_score" in hits[0]
