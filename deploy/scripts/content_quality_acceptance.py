from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from shannon.quality import (
    QualityEvaluationInput,
    compare_with_baseline,
    evaluate_content_quality,
    generate_quality_report,
    load_baseline_scores,
    load_quality_scoring_config,
    save_baseline_scores,
)


def _extract_correctness_metrics(report: Dict[str, Any]) -> Dict[str, float]:
    dimensions = report.get("dimensions") if isinstance(report.get("dimensions"), dict) else {}
    correctness = dimensions.get("correctness") if isinstance(dimensions.get("correctness"), dict) else {}
    diagnostics = correctness.get("diagnostics") if isinstance(correctness.get("diagnostics"), list) else []
    for item in diagnostics:
        if isinstance(item, dict) and isinstance(item.get("summary"), dict):
            summary = item["summary"]
            return {
                "unsupported_ratio": float(summary.get("unsupported_ratio", 0.0)),
                "pseudo_false_negative_ratio": float(summary.get("pseudo_false_negative_ratio", 0.0)),
            }
    return {"unsupported_ratio": 0.0, "pseudo_false_negative_ratio": 0.0}


def _load_samples(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("samples file must be object")
    return data


def _evaluate_samples(samples: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, float]]]:
    config = load_quality_scoring_config()
    reports: List[Dict[str, Any]] = []
    score_map: Dict[str, Dict[str, float]] = {}

    for sample in samples:
        sample_id = str(sample.get("sample_id") or "unknown")
        payload = QualityEvaluationInput(
            content=str(sample.get("content") or ""),
            evidence=[str(item) for item in sample.get("evidence", []) if item],
            key_points=[str(item) for item in sample.get("key_points", []) if item],
            task_goal=str(sample.get("task_goal") or ""),
            target_user=str(sample.get("target_user") or ""),
        )
        result = evaluate_content_quality(payload, config)
        report = generate_quality_report(payload, result)
        report["sample_id"] = sample_id
        reports.append(report)
        correctness_metrics = _extract_correctness_metrics(report)
        score_map[sample_id] = {
            "correctness": result.dimensions["correctness"].score,
            "completeness": result.dimensions["completeness"].score,
            "structure": result.dimensions["structure"].score,
            "usability": result.dimensions["usability"].score,
            "total": result.total_score,
            "unsupported_ratio": correctness_metrics["unsupported_ratio"],
            "pseudo_false_negative_ratio": correctness_metrics["pseudo_false_negative_ratio"],
        }

    return reports, score_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Content quality acceptance runner")
    parser.add_argument("--samples", default="reports/content_quality/samples/v1/samples.json")
    parser.add_argument("--report", default="reports/content_quality/latest_report.json")
    parser.add_argument("--baseline", default="reports/content_quality/baseline/v1_baseline.json")
    parser.add_argument("--mode", choices=["single", "regression", "refresh-baseline"], default="single")
    args = parser.parse_args()

    samples_path = Path(args.samples)
    report_path = Path(args.report)
    baseline_path = Path(args.baseline)

    sample_doc = _load_samples(samples_path)
    samples = sample_doc.get("samples") if isinstance(sample_doc.get("samples"), list) else []
    dataset_version = str(sample_doc.get("dataset_version") or "")

    reports, score_map = _evaluate_samples(samples)
    report_payload: Dict[str, Any] = {
        "dataset_version": dataset_version,
        "mode": args.mode,
        "sample_count": len(samples),
        "reports": reports,
    }

    if args.mode == "refresh-baseline":
        metric_unsupported = [float(item.get("unsupported_ratio", 0.0)) for item in score_map.values()]
        metric_pfn = [float(item.get("pseudo_false_negative_ratio", 0.0)) for item in score_map.values()]
        aggregate_metrics = {
            "unsupported_ratio": (sum(metric_unsupported) / len(metric_unsupported)) if metric_unsupported else 0.0,
            "pseudo_false_negative_ratio": (sum(metric_pfn) / len(metric_pfn)) if metric_pfn else 0.0,
        }
        baseline = save_baseline_scores(
            sample_scores=score_map,
            dataset_version=dataset_version,
            output_path=baseline_path,
            change_note="baseline refreshed by acceptance script",
            correctness_metrics=aggregate_metrics,
        )
        report_payload["baseline"] = baseline
    elif args.mode == "regression":
        baseline = load_baseline_scores(baseline_path)
        summary = compare_with_baseline(baseline=baseline, current_scores=score_map)
        report_payload["regression_summary"] = summary

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"content quality acceptance done, report={report_path}")


if __name__ == "__main__":
    main()