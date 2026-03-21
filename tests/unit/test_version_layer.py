from __future__ import annotations

import subprocess
from pathlib import Path

from shannon.storage.version_layer.git_version_store import GitVersionStore


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "command failed")
    return proc.stdout.strip()


def test_version_layer_commit_and_tag(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "unit@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "unit-bot"], cwd=repo)

    seed = repo / "README.md"
    seed.write_text("seed\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-m", "seed"], cwd=repo)

    store = GitVersionStore(repo_root=str(repo))
    target = repo / "reports" / "run-1" / "agent" / "task-1" / "final.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")

    commit = store.commit_task(
        run_id="run-1",
        task_id="task-1",
        stage="phase-3",
        files=[str(target)],
        quality_score=0.9,
        decay_score=0.8,
    )
    assert commit["status"] in {"committed", "skipped"}

    tag = store.create_stage_tag("run-1", "phase-3")
    assert tag["status"] in {"created", "exists"}


def test_version_layer_forbid_merge_rebase(tmp_path: Path):
    store = GitVersionStore(repo_root=str(tmp_path))

    merge_blocked = False
    try:
        store.reject_forbidden_operation("merge")
    except ValueError:
        merge_blocked = True
    assert merge_blocked

    rebase_blocked = False
    try:
        store.reject_forbidden_operation("rebase")
    except ValueError:
        rebase_blocked = True
    assert rebase_blocked
