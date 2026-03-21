from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

# 中文注释：版本层（Git CLI）实现，append-only 策略


class GitVersionStore:
    # 中文注释：函数 __init__ 的入口
    def __init__(self, repo_root: str | None = None) -> None:
        configured = (repo_root or os.getenv("VERSION_LAYER_REPO_ROOT") or ".").strip()
        self.repo_root = Path(configured).expanduser().resolve()

    # 中文注释：函数 _run_git 的入口
    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )

    # 中文注释：函数 reject_forbidden_operation 的入口
    def reject_forbidden_operation(self, operation: str) -> None:
        op = str(operation or "").strip().lower()
        if op in {"rebase", "merge"}:
            raise ValueError(f"append-only policy forbids git {op}")

    # 中文注释：函数 _ensure_repo 的入口
    def _ensure_repo(self) -> None:
        result = self._run_git(["rev-parse", "--is-inside-work-tree"])
        if result.returncode != 0:
            raise RuntimeError("not a git repository")

    # 中文注释：函数 commit_task 的入口
    def commit_task(
        self,
        *,
        run_id: str,
        task_id: str,
        stage: str,
        files: List[str],
        quality_score: float,
        decay_score: float,
        message: str | None = None,
    ) -> Dict[str, Any]:
        self._ensure_repo()
        self.reject_forbidden_operation("commit")

        existing_files = [str(Path(path).resolve()) for path in files if Path(path).exists()]
        if not existing_files:
            return {"status": "skipped", "reason": "no_files"}

        add_result = self._run_git(["add", *existing_files])
        if add_result.returncode != 0:
            raise RuntimeError(add_result.stderr.strip() or "git add failed")

        status_result = self._run_git(["status", "--porcelain"])
        if status_result.returncode != 0:
            raise RuntimeError(status_result.stderr.strip() or "git status failed")
        if not status_result.stdout.strip():
            return {"status": "skipped", "reason": "no_changes"}

        commit_message = (
            message
            or f"task:{task_id}: append report"
        )
        body = (
            f"run_id: {run_id}\n"
            f"task_id: {task_id}\n"
            f"stage: {stage}\n"
            f"quality_score: {quality_score:.4f}\n"
            f"decay_score: {decay_score:.4f}\n"
            "policy: append-only\n"
        )
        commit_result = self._run_git(["commit", "-m", commit_message, "-m", body])
        if commit_result.returncode != 0:
            stderr = commit_result.stderr.strip()
            if "nothing to commit" in stderr.lower():
                return {"status": "skipped", "reason": "nothing_to_commit"}
            raise RuntimeError(stderr or "git commit failed")

        sha_result = self._run_git(["rev-parse", "HEAD"])
        sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
        return {"status": "committed", "sha": sha, "message": commit_message}

    # 中文注释：函数 create_stage_tag 的入口
    def create_stage_tag(self, run_id: str, stage: str) -> Dict[str, Any]:
        self._ensure_repo()
        self.reject_forbidden_operation("tag")
        tag = f"stage/{run_id}/{stage}"

        exists_result = self._run_git(["tag", "--list", tag])
        if exists_result.returncode == 0 and exists_result.stdout.strip() == tag:
            return {"status": "exists", "tag": tag}

        create_result = self._run_git(["tag", tag])
        if create_result.returncode != 0:
            raise RuntimeError(create_result.stderr.strip() or "git tag failed")
        return {"status": "created", "tag": tag}

    # 中文注释：函数 append_log 的入口
    def append_log(self, run_id: str, payload: Dict[str, Any]) -> str:
        log_dir = self.repo_root / "reports" / str(run_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        target = log_dir / "version_log.jsonl"
        row = {"timestamp": time.time(), **payload}
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return str(target)


git_version_store = GitVersionStore()
