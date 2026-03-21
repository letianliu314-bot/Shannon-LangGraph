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
    correctness_metrics: Dict[str, float] | None = None,
) -> Dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_version": dataset_version,
        "updated_at": time.time(),
        "change_note": change_note,
        "samples": sample_scores,
        "correctness_metrics": correctness_metrics or {},
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
    calibration_thresholds: Dict[str, float] | None = None,
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

    thresholds = calibration_thresholds or {
        "unsupported_ratio": 0.45,
        "pseudo_false_negative_ratio": 0.25,
    }

    def _aggregate_metrics(samples: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        unsupported_values: List[float] = []
        pfn_values: List[float] = []
        for score_item in samples.values():
            if "unsupported_ratio" in score_item:
                unsupported_values.append(float(score_item.get("unsupported_ratio", 0.0)))
            if "pseudo_false_negative_ratio" in score_item:
                pfn_values.append(float(score_item.get("pseudo_false_negative_ratio", 0.0)))
        return {
            "unsupported_ratio": (sum(unsupported_values) / len(unsupported_values)) if unsupported_values else 0.0,
            "pseudo_false_negative_ratio": (sum(pfn_values) / len(pfn_values)) if pfn_values else 0.0,
        }

    current_metrics = _aggregate_metrics(current_scores)
    baseline_metrics = baseline.get("correctness_metrics") if isinstance(baseline.get("correctness_metrics"), dict) else _aggregate_metrics(base_samples)

    metric_regressions: List[Dict[str, Any]] = []
    for metric_name in ["unsupported_ratio", "pseudo_false_negative_ratio"]:
        current_value = float(current_metrics.get(metric_name, 0.0))
        baseline_value = float(baseline_metrics.get(metric_name, current_value))
        delta = current_value - baseline_value
        if delta > abs(tolerance):
            metric_regressions.append(
                {
                    "metric": metric_name,
                    "baseline": baseline_value,
                    "current": current_value,
                    "delta": delta,
                }
            )

    drift_alerts: List[Dict[str, Any]] = []
    for metric_name, threshold in thresholds.items():
        current_value = float(current_metrics.get(metric_name, 0.0))
        if current_value > float(threshold):
            drift_alerts.append(
                {
                    "type": "calibration_drift",
                    "metric": metric_name,
                    "threshold": float(threshold),
                    "current": current_value,
                }
            )

    return {
        "dataset_version": baseline.get("dataset_version", ""),
        "compared_at": time.time(),
        "tolerance": tolerance,
        "regression_count": len(regressions),
        "has_regression": len(regressions) > 0,
        "regressions": regressions,
        "correctness_metrics": {
            "baseline": baseline_metrics,
            "current": current_metrics,
            "metric_regressions": metric_regressions,
        },
        "calibration_drift": len(drift_alerts) > 0,
        "alerts": drift_alerts,
    }