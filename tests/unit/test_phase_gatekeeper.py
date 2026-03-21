from __future__ import annotations

from pathlib import Path

from shannon.orchestration.orchestrator.gatekeeper import PhaseGatekeeper
from shannon.storage.memory_layer.store import SharedMemoryStore


def test_phase_gatekeeper_blocks_until_previous_phase_passed(tmp_path: Path):
    store = SharedMemoryStore(root_dir=str(tmp_path / "reports"))
    store.ensure_run_manifest("run-1")

    keeper = PhaseGatekeeper()
    keeper._gate_file = lambda run_id, phase: store._run_dir(run_id) / "stages" / phase / "gate.json"  # type: ignore[attr-defined]
    keeper._gate_log = lambda run_id: store._run_dir(run_id) / "stages" / "gate_log.jsonl"  # type: ignore[attr-defined]

    blocked = keeper.can_enter("run-1", "phase-2")
    assert blocked["allowed"] is False

    keeper.record_decision("run-1", "phase-1", "passed", "ok")
    allowed = keeper.can_enter("run-1", "phase-2")
    assert allowed["allowed"] is True


def test_phase_gatekeeper_rejects_invalid_status(tmp_path: Path):
    store = SharedMemoryStore(root_dir=str(tmp_path / "reports"))
    store.ensure_run_manifest("run-2")

    keeper = PhaseGatekeeper()
    keeper._gate_file = lambda run_id, phase: store._run_dir(run_id) / "stages" / phase / "gate.json"  # type: ignore[attr-defined]
    keeper._gate_log = lambda run_id: store._run_dir(run_id) / "stages" / "gate_log.jsonl"  # type: ignore[attr-defined]

    raised = False
    try:
        keeper.record_decision("run-2", "phase-1", "unknown", "bad")
    except ValueError:
        raised = True
    assert raised
