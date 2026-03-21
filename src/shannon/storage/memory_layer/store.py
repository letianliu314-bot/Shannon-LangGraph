from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 中文注释：外部共享记忆层（单分支 + run 目录隔离）


class SharedMemoryStore:
    # 中文注释：函数 __init__ 的入口
    def __init__(self, root_dir: str | None = None) -> None:
        configured = (root_dir or os.getenv("SHARED_MEMORY_ROOT") or "reports").strip()
        self.root_dir = Path(configured).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    # 中文注释：函数 _sanitize_component 的入口
    def _sanitize_component(self, value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip())
        cleaned = cleaned.strip(".-")
        return cleaned or fallback

    # 中文注释：函数 _run_dir 的入口
    def _run_dir(self, run_id: str) -> Path:
        run_component = self._sanitize_component(run_id, "run")
        return self.root_dir / run_component

    # 中文注释：函数 _safe_relative_path 的入口
    def _safe_relative_path(self, rel_path: str) -> str:
        candidate = Path(rel_path)
        if candidate.is_absolute():
            raise ValueError("absolute path is not allowed")
        normalized = Path(str(candidate).replace("\\", "/"))
        parts = [part for part in normalized.parts if part not in {"", "."}]
        if any(part == ".." for part in parts):
            raise ValueError("path traversal is not allowed")
        return "/".join(parts)

    # 中文注释：函数 ensure_run_manifest 的入口
    def ensure_run_manifest(self, run_id: str, manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = run_dir / "run_manifest.json"
        now = time.time()

        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        payload = {
            "run_id": self._sanitize_component(run_id, "run"),
            "created_at": now,
            "layout_version": "v1",
            "policy": {
                "single_branch": True,
                "append_only": True,
                "forbid_rebase": True,
                "forbid_merge": True,
            },
            "stage": "phase-1",
        }
        if isinstance(manifest, dict):
            payload.update(manifest)
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    # 中文注释：函数 write_run_file 的入口
    def write_run_file(self, run_id: str, rel_path: str, content: str) -> str:
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        safe_rel = self._safe_relative_path(rel_path)
        target = run_dir / safe_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        return str(target)

    # 中文注释：函数 upsert_task_record 的入口
    def upsert_task_record(
        self,
        run_id: str,
        task_id: str,
        content: str,
        *,
        stage: str = "phase-1",
        capability: str = "general",
        agent: str = "orchestrator",
        artifact_name: str = "final.md",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        safe_task = self._sanitize_component(task_id, "task")
        safe_agent = self._sanitize_component(agent, "agent")
        safe_stage = self._sanitize_component(stage, "phase")
        safe_capability = self._sanitize_component(capability, "general")
        safe_artifact = self._sanitize_component(artifact_name, "final.md")

        self.ensure_run_manifest(run_id)
        rel_dir = f"{safe_agent}/{safe_task}"
        report_path = self.write_run_file(run_id, f"{rel_dir}/{safe_artifact}", content)

        payload: Dict[str, Any] = {
            "run_id": self._sanitize_component(run_id, "run"),
            "task_id": safe_task,
            "stage": safe_stage,
            "capability": safe_capability,
            "agent": safe_agent,
            "artifact_path": str(Path(report_path).relative_to(self.root_dir)),
            "artifact_abs_path": report_path,
            "artifact_name": safe_artifact,
            "timestamp": time.time(),
            "content": str(content),
        }
        if isinstance(metadata, dict):
            payload["metadata"] = metadata

        meta_path = self._run_dir(run_id) / rel_dir / "meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["meta_path"] = str(meta_path.relative_to(self.root_dir))
        payload["meta_abs_path"] = str(meta_path)

        index_path = self._run_dir(run_id) / "memory_index.jsonl"
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        payload["index_path"] = str(index_path.relative_to(self.root_dir))
        payload["index_abs_path"] = str(index_path)
        return payload

    # 中文注释：函数 search_records 的入口
    def search_records(
        self,
        *,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        stage: Optional[str] = None,
        capability: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        bounded_limit = max(1, min(int(limit or 20), 200))
        run_filter = self._sanitize_component(run_id, "run") if run_id else None
        task_filter = self._sanitize_component(task_id, "task") if task_id else None
        stage_filter = self._sanitize_component(stage, "phase") if stage else None
        capability_filter = self._sanitize_component(capability, "general") if capability else None

        run_dirs: List[Path]
        if run_filter:
            run_dirs = [self._run_dir(run_filter)]
        else:
            run_dirs = [item for item in self.root_dir.iterdir() if item.is_dir()]

        records: List[Dict[str, Any]] = []
        for run_dir in run_dirs:
            index_path = run_dir / "memory_index.jsonl"
            if not index_path.exists():
                continue
            try:
                lines = index_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            for line in lines:
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if not isinstance(item, dict):
                    continue
                if run_filter and str(item.get("run_id")) != run_filter:
                    continue
                if task_filter and str(item.get("task_id")) != task_filter:
                    continue
                if stage_filter and str(item.get("stage")) != stage_filter:
                    continue
                if capability_filter and str(item.get("capability")) != capability_filter:
                    continue
                records.append(item)

        now = time.time()

        def _score(row: Dict[str, Any]) -> Dict[str, Any]:
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            quality_raw = metadata.get("quality_score") if isinstance(metadata, dict) else None
            try:
                quality_score = max(0.0, min(float(quality_raw), 1.0))
            except Exception:
                quality_score = 0.5

            ts = float(row.get("timestamp") or now)
            age_seconds = max(0.0, now - ts)
            half_life_days = 30.0
            decay_score = 0.5 ** (age_seconds / (half_life_days * 24.0 * 3600.0))

            # 中文注释：质量优先，且时间衰减为必选项
            w_q = 0.7
            w_t = 0.3
            final_score = (w_q * quality_score) + (w_t * decay_score)

            enriched = dict(row)
            enriched["quality_score"] = quality_score
            enriched["decay_score"] = decay_score
            enriched["final_score"] = final_score
            return enriched

        scored = [_score(item) for item in records]
        scored.sort(key=lambda value: float(value.get("final_score") or 0.0), reverse=True)
        return scored[:bounded_limit]


shared_memory_store = SharedMemoryStore()
