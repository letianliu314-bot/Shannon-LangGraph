from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from shannon.storage.memory_layer import shared_memory_store

# 中文注释：阶段门禁状态机（phase-1..phase-5，失败冻结）

_PHASE_ORDER = ["phase-1", "phase-2", "phase-3", "phase-4", "phase-5"]


class PhaseGatekeeper:
    # 中文注释：函数 _phase_index 的入口
    def _phase_index(self, phase: str) -> int:
        normalized = str(phase or "").strip().lower()
        if normalized not in _PHASE_ORDER:
            raise ValueError(f"invalid phase: {phase}")
        return _PHASE_ORDER.index(normalized)

    # 中文注释：函数 _gate_file 的入口
    def _gate_file(self, run_id: str, phase: str) -> Path:
        run_dir = shared_memory_store._run_dir(run_id)
        return run_dir / "stages" / phase / "gate.json"

    # 中文注释：函数 _gate_log 的入口
    def _gate_log(self, run_id: str) -> Path:
        run_dir = shared_memory_store._run_dir(run_id)
        return run_dir / "stages" / "gate_log.jsonl"

    # 中文注释：函数 _read_gate 的入口
    def _read_gate(self, run_id: str, phase: str) -> Dict[str, Any] | None:
        gate_path = self._gate_file(run_id, phase)
        if not gate_path.exists():
            return None
        try:
            payload = json.loads(gate_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    # 中文注释：函数 can_enter 的入口
    def can_enter(self, run_id: str, phase: str) -> Dict[str, Any]:
        idx = self._phase_index(phase)
        if idx == 0:
            return {"allowed": True, "gate_status": "open", "reason": "phase-1 always allowed"}

        for prev_idx in range(idx):
            prev_phase = _PHASE_ORDER[prev_idx]
            prev_gate = self._read_gate(run_id, prev_phase)
            if not prev_gate:
                return {
                    "allowed": False,
                    "gate_status": "frozen",
                    "reason": f"previous phase not passed: {prev_phase}",
                }

            prev_status = str(prev_gate.get("status") or "").lower()
            if prev_status == "passed":
                continue
            if prev_status == "failed":
                return {
                    "allowed": False,
                    "gate_status": "frozen",
                    "reason": f"previous phase failed: {prev_phase}",
                }
            if prev_status == "warning":
                metadata = prev_gate.get("metadata") if isinstance(prev_gate.get("metadata"), dict) else {}
                quality = metadata.get("quality") if isinstance(metadata.get("quality"), dict) else {}
                allow_warning = bool(
                    metadata.get("allow_warning_pass")
                    or quality.get("allow_warning_pass")
                )
                if allow_warning:
                    continue
                return {
                    "allowed": False,
                    "gate_status": "frozen",
                    "reason": f"previous phase warning requires explicit allow: {prev_phase}",
                }
            return {
                "allowed": False,
                "gate_status": "frozen",
                "reason": f"previous phase invalid status: {prev_phase}",
            }

        return {"allowed": True, "gate_status": "open", "reason": "all previous phases passed"}

    # 中文注释：函数 record_decision 的入口
    def record_decision(self, run_id: str, phase: str, status: str, reason: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"passed", "failed", "warning"}:
            raise ValueError("status must be passed|failed|warning")

        payload: Dict[str, Any] = {
            "run_id": run_id,
            "phase": phase,
            "status": normalized_status,
            "reason": str(reason or ""),
            "timestamp": time.time(),
        }
        if isinstance(metadata, dict):
            payload["metadata"] = metadata

        gate_file = self._gate_file(run_id, phase)
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        log_path = self._gate_log(run_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

        return payload


phase_gatekeeper = PhaseGatekeeper()
