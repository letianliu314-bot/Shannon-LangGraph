from __future__ import annotations

import subprocess
from pathlib import Path

from shannon.storage.version_layer.git_version_store import GitVersionStore


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "command failed")
    return proc.stdout.strip()


def run_checks() -> None:
    repo = Path("reports/_phase3_acceptance_repo").resolve()
    if repo.exists():
        _run(["rm", "-rf", str(repo)], cwd=Path(".").resolve())
    repo.mkdir(parents=True, exist_ok=True)

    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "phase3@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "phase3-bot"], cwd=repo)

    base = repo / "README.md"
    base.write_text("seed\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-m", "seed"], cwd=repo)

    store = GitVersionStore(repo_root=str(repo))

    f1 = repo / "reports" / "run-a" / "agent" / "task-1" / "final.md"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("task-1 output", encoding="utf-8")
    result1 = store.commit_task(
        run_id="run-a",
        task_id="task-1",
        stage="phase-3",
        files=[str(f1)],
        quality_score=0.9,
        decay_score=0.8,
    )
    assert result1["status"] in {"committed", "skipped"}

    f2 = repo / "reports" / "run-a" / "agent" / "task-2" / "final.md"
    f2.parent.mkdir(parents=True, exist_ok=True)
    f2.write_text("task-2 output", encoding="utf-8")
    result2 = store.commit_task(
        run_id="run-a",
        task_id="task-2",
        stage="phase-3",
        files=[str(f2)],
        quality_score=0.95,
        decay_score=0.82,
    )
    assert result2["status"] in {"committed", "skipped"}

    tag_result = store.create_stage_tag("run-a", "phase-3")
    assert tag_result["status"] in {"created", "exists"}

    blocked = False
    try:
        store.reject_forbidden_operation("merge")
    except ValueError:
        blocked = True
    assert blocked

    print("Phase 3 acceptance passed")


if __name__ == "__main__":
    run_checks()
