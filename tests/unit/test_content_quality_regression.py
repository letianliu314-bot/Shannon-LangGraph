from __future__ import annotations

from pathlib import Path

from shannon.quality.regression import compare_with_baseline, load_baseline_scores, save_baseline_scores


def test_baseline_persistence_and_compare(tmp_path: Path):
    baseline_path = tmp_path / "baseline.json"
    baseline = save_baseline_scores(
        sample_scores={
            "sample-1": {
                "correctness": 0.9,
                "completeness": 0.8,
                "structure": 0.8,
                "usability": 0.8,
                "total": 0.85,
            }
        },
        dataset_version="v1",
        output_path=baseline_path,
        change_note="initial baseline",
    )

    loaded = load_baseline_scores(baseline_path)
    assert loaded["dataset_version"] == "v1"
    assert baseline["samples"]["sample-1"]["total"] == loaded["samples"]["sample-1"]["total"]

    summary = compare_with_baseline(
        baseline=loaded,
        current_scores={
            "sample-1": {
                "correctness": 0.7,
                "completeness": 0.8,
                "structure": 0.8,
                "usability": 0.8,
                "total": 0.78,
            }
        },
        tolerance=0.05,
    )
    assert summary["has_regression"] is True
    assert summary["regression_count"] >= 1