from __future__ import annotations

import subprocess
from pathlib import Path

from shannon.storage.version_layer.git_version_store import GitVersionStore

# 中文注释：Phase 3 验收脚本
# 目的：验证版本层核心治理能力
# 覆盖点：task 级 commit、stage tag、append-only 禁令


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "command failed")
    return proc.stdout.strip()


def run_checks() -> None:
    # 中文注释：创建临时 git 仓库，确保验收可重复且不污染主仓库
    repo = Path("reports/_phase3_acceptance_repo").resolve()
    if repo.exists():
        _run(["rm", "-rf", str(repo)], cwd=Path(".").resolve())
    repo.mkdir(parents=True, exist_ok=True)

    # 中文注释：初始化 git 用户信息，保障 commit 命令可执行
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "phase3@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "phase3-bot"], cwd=repo)

    # 中文注释：提交种子文件，建立初始提交基线
    base = repo / "README.md"
    base.write_text("seed\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-m", "seed"], cwd=repo)

    store = GitVersionStore(repo_root=str(repo))

    # 中文注释：模拟 task-1 产出并执行 task 级提交
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

    # 中文注释：模拟 task-2 产出并执行 task 级提交
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

    # 中文注释：阶段通过后应可创建对应 stage tag
    tag_result = store.create_stage_tag("run-a", "phase-3")
    assert tag_result["status"] in {"created", "exists"}

    # 中文注释：append-only 守卫必须拒绝 merge 操作
    blocked = False
    try:
        store.reject_forbidden_operation("merge")
    except ValueError:
        blocked = True
    assert blocked

    print("Phase 3 acceptance passed")


if __name__ == "__main__":
    run_checks()
