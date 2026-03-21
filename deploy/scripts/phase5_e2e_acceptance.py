from __future__ import annotations

import subprocess
from pathlib import Path

from shannon.llm_service.main import TaskContract, _resolve_prompt_contract
from shannon.orchestration.orchestrator.gatekeeper import PhaseGatekeeper
from shannon.storage.memory_layer.store import SharedMemoryStore
from shannon.storage.version_layer.git_version_store import GitVersionStore

# 中文注释：Phase 5 端到端验收脚本
# 目的：串联验证 Memory/Prompt/Version/Gatekeeper 四层协同
# 覆盖点：排序字段完整性、prompt 降级容错、append-only 守卫、阶段放行链路


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "command failed")
    return proc.stdout.strip()


def run_checks() -> None:
    # 中文注释：1) Memory Layer + ranking
    # 验证质量分与时间衰减字段已写入并可被检索返回
    root = Path("reports/_phase5_acceptance_tmp").resolve()
    if root.exists():
        _run(["rm", "-rf", str(root)], cwd=Path(".").resolve())
    store = SharedMemoryStore(root_dir=str(root))
    store.ensure_run_manifest("run-e2e")
    store.upsert_task_record(
        run_id="run-e2e",
        task_id="task-a",
        content="A",
        stage="phase-5",
        capability="ranking",
        metadata={"quality_score": 0.95},
    )
    store.upsert_task_record(
        run_id="run-e2e",
        task_id="task-b",
        content="B",
        stage="phase-5",
        capability="ranking",
        metadata={"quality_score": 0.2},
    )
    hits = store.search_records(run_id="run-e2e", capability="ranking", limit=10)
    assert hits and "quality_score" in hits[0] and "decay_score" in hits[0] and "final_score" in hits[0]

    # 中文注释：2) Prompt Expert integration
    # 允许主路径或 fallback，确保端到端链路不会因模型异常中断
    task = TaskContract(id="task-1", title="infra", goal="analyze", description="analyze", deliverable="summary")
    _, meta = _resolve_prompt_contract(task=task, user_request="analyze infra", refined={})
    assert meta["status"] in {"ok", "fallback"}

    # 中文注释：3) Version Layer + append-only guard
    # 在临时仓库中验证 task 提交与禁止 merge/rebase 规则
    repo = Path("reports/_phase5_acceptance_repo").resolve()
    if repo.exists():
        _run(["rm", "-rf", str(repo)], cwd=Path(".").resolve())
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "phase5@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "phase5-bot"], cwd=repo)
    seed = repo / "README.md"
    seed.write_text("seed\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-m", "seed"], cwd=repo)

    version = GitVersionStore(repo_root=str(repo))
    target = repo / "reports" / "run-e2e" / "agent" / "task-1" / "final.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("result", encoding="utf-8")
    commit = version.commit_task(
        run_id="run-e2e",
        task_id="task-1",
        stage="phase-5",
        files=[str(target)],
        quality_score=0.9,
        decay_score=0.8,
    )
    assert commit["status"] in {"committed", "skipped"}
    version.reject_forbidden_operation("commit")

    merge_blocked = False
    try:
        version.reject_forbidden_operation("merge")
    except ValueError:
        merge_blocked = True
    assert merge_blocked

    # 中文注释：4) Gatekeeper end-to-end check
    # 当前置 phase 全部通过时，phase-5 必须放行
    keeper = PhaseGatekeeper()
    keeper._gate_file = lambda run_id, phase: store._run_dir(run_id) / "stages" / phase / "gate.json"  # type: ignore[attr-defined]
    keeper._gate_log = lambda run_id: store._run_dir(run_id) / "stages" / "gate_log.jsonl"  # type: ignore[attr-defined]
    keeper.record_decision("run-e2e", "phase-1", "passed", "ok")
    keeper.record_decision("run-e2e", "phase-2", "passed", "ok")
    keeper.record_decision("run-e2e", "phase-3", "passed", "ok")
    keeper.record_decision("run-e2e", "phase-4", "passed", "ok")
    can_enter_phase5 = keeper.can_enter("run-e2e", "phase-5")
    assert can_enter_phase5["allowed"] is True

    print("Phase 5 acceptance passed")


if __name__ == "__main__":
    run_checks()
