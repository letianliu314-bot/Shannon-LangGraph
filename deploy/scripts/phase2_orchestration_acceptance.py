from __future__ import annotations

import shutil
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from shannon.orchestration.orchestrator.gatekeeper import PhaseGatekeeper
from shannon.orchestration.orchestrator.graph import build_graph
from shannon.storage.memory_layer.store import SharedMemoryStore


def run_checks() -> None:
    root = Path("reports/_phase2_acceptance_tmp")
    if root.exists():
        shutil.rmtree(root)

    # 门禁阻断与放行
    store = SharedMemoryStore(root_dir=str(root))
    _ = store.ensure_run_manifest("run-phase2")
    gatekeeper = PhaseGatekeeper()

    # monkey patch gatekeeper to use acceptance root
    gatekeeper._gate_file = lambda run_id, phase: store._run_dir(run_id) / "stages" / phase / "gate.json"  # type: ignore[attr-defined]
    gatekeeper._gate_log = lambda run_id: store._run_dir(run_id) / "stages" / "gate_log.jsonl"  # type: ignore[attr-defined]

    blocked = gatekeeper.can_enter("run-phase2", "phase-2")
    assert blocked["allowed"] is False
    assert blocked["gate_status"] == "frozen"

    gatekeeper.record_decision("run-phase2", "phase-1", "passed", "phase-1 accepted")
    allowed = gatekeeper.can_enter("run-phase2", "phase-2")
    assert allowed["allowed"] is True
    assert allowed["gate_status"] == "open"

    # DAG 兼容性：编排图可正常编译
    graph = build_graph(MemorySaver())
    assert graph is not None

    print("Phase 2 acceptance passed")


if __name__ == "__main__":
    run_checks()
