from __future__ import annotations

import shutil
from pathlib import Path

from shannon.storage.memory_layer.store import SharedMemoryStore

# 中文注释：Phase 1 验收脚本
# 目的：验证共享记忆层的最小可靠性基线
# 覆盖点：run 目录隔离、跨 run 写保护、按条件检索准确性


def run_checks() -> None:
    # 中文注释：使用独立临时目录，避免污染正式 reports 数据
    root = Path("reports/_phase1_acceptance_tmp")
    if root.exists():
        shutil.rmtree(root)

    store = SharedMemoryStore(root_dir=str(root))

    # 中文注释：检查不同 run 是否生成各自独立的 manifest
    manifest_a = store.ensure_run_manifest("run-a")
    manifest_b = store.ensure_run_manifest("run-b")
    assert manifest_a["run_id"] == "run-a"
    assert manifest_b["run_id"] == "run-b"
    assert (root / "run-a" / "run_manifest.json").exists()
    assert (root / "run-b" / "run_manifest.json").exists()

    # 中文注释：路径穿越攻击应被阻断，防止跨 run 覆盖写
    blocked = False
    try:
        store.write_run_file("run-a", "../run-b/hack.md", "bad")
    except ValueError:
        blocked = True
    assert blocked, "path traversal must be blocked"

    # 中文注释：写入两条不同 capability 的记录，验证过滤检索
    store.upsert_task_record(
        run_id="run-a",
        task_id="task-1",
        content="infra gpu supply chain analysis",
        stage="phase-1",
        capability="infra",
        agent="infra-agent",
        metadata={"quality_score": 0.92, "decay_score": 0.81},
    )
    store.upsert_task_record(
        run_id="run-a",
        task_id="task-2",
        content="memory layer overview",
        stage="phase-1",
        capability="memory",
        agent="memory-agent",
        metadata={"quality_score": 0.88, "decay_score": 0.80},
    )

    infra_hits = store.search_records(run_id="run-a", capability="infra", limit=10)
    assert len(infra_hits) == 1
    assert infra_hits[0]["task_id"] == "task-1"

    phase_hits = store.search_records(run_id="run-a", stage="phase-1", limit=10)
    assert len(phase_hits) == 2

    print("Phase 1 acceptance passed")


if __name__ == "__main__":
    run_checks()
