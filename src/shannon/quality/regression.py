from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


def save_baseline_scores(
    sample_scores: Dict[str, Dict[str, float]],
    dataset_version: str,
    output_path: str | Path,
    change_note: str = "",
) -> Dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_version": dataset_version,
        "updated_at": time.time(),
        "change_note": change_note,
        "samples": sample_scores,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_baseline_scores(path: str | Path) -> Dict[str, Any]:
    baseline_path = Path(path)
    if not baseline_path.exists():
        return {"dataset_version": "", "samples": {}}
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"dataset_version": "", "samples": {}}
    samples = data.get("samples") if isinstance(data.get("samples"), dict) else {}
    data["samples"] = samples
    return data


def compare_with_baseline(
    baseline: Dict[str, Any],
    current_scores: Dict[str, Dict[str, float]],
    tolerance: float = 0.05,
) -> Dict[str, Any]:
    base_samples = baseline.get("samples") if isinstance(baseline.get("samples"), dict) else {}
    regressions: List[Dict[str, Any]] = []

    for sample_id, current in current_scores.items():
        base = base_samples.get(sample_id) if isinstance(base_samples.get(sample_id), dict) else {}
        for dim in ["correctness", "completeness", "structure", "usability", "total"]:
            current_value = float(current.get(dim, 0.0))
            base_value = float(base.get(dim, current_value))
            delta = current_value - base_value
            if delta < -abs(tolerance):
                severity = "high" if delta <= -0.2 else "medium" if delta <= -0.1 else "low"
                regressions.append(
                    {
                        "sample_id": sample_id,
                        "dimension": dim,
                        "baseline": base_value,
                        "current": current_value,
                        "delta": delta,
                        "severity": severity,
                    }
                )

    return {
        "dataset_version": baseline.get("dataset_version", ""),
        "compared_at": time.time(),
        "tolerance": tolerance,
        "regression_count": len(regressions),
        "has_regression": len(regressions) > 0,
        "regressions": regressions,
    }