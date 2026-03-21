from __future__ import annotations

import shutil
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from shannon.orchestration.orchestrator.gatekeeper import PhaseGatekeeper
from shannon.orchestration.orchestrator.graph import build_graph
from shannon.storage.memory_layer.store import SharedMemoryStore

# 中文注释：Phase 2 验收脚本
# 目的：验证编排层门禁策略与图构建兼容性
# 覆盖点：阶段阻断/放行、DAG 编译能力


def run_checks() -> None:
    # 中文注释：使用隔离目录构造一次独立 gate 验收环境
    root = Path("reports/_phase2_acceptance_tmp")
    if root.exists():
        shutil.rmtree(root)

    # 中文注释：先验证 phase-2 在 phase-1 未通过时会被冻结
    store = SharedMemoryStore(root_dir=str(root))
    _ = store.ensure_run_manifest("run-phase2")
    gatekeeper = PhaseGatekeeper()

    # 中文注释：测试中把 gate 文件指向临时目录，避免影响真实数据
    gatekeeper._gate_file = lambda run_id, phase: store._run_dir(run_id) / "stages" / phase / "gate.json"  # type: ignore[attr-defined]
    gatekeeper._gate_log = lambda run_id: store._run_dir(run_id) / "stages" / "gate_log.jsonl"  # type: ignore[attr-defined]

    blocked = gatekeeper.can_enter("run-phase2", "phase-2")
    assert blocked["allowed"] is False
    assert blocked["gate_status"] == "frozen"

    # 中文注释：写入 phase-1 passed 后，phase-2 应该可进入
    gatekeeper.record_decision("run-phase2", "phase-1", "passed", "phase-1 accepted")
    allowed = gatekeeper.can_enter("run-phase2", "phase-2")
    assert allowed["allowed"] is True
    assert allowed["gate_status"] == "open"

    # 中文注释：确认引入 gate 逻辑后，编排图仍可编译
    graph = build_graph(MemorySaver())
    assert graph is not None

    print("Phase 2 acceptance passed")


if __name__ == "__main__":
    run_checks()
