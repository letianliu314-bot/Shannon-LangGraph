from __future__ import annotations

from shannon.quality.paradigm_testing import (
    evaluate_json_content,
    evaluate_report_content,
    infer_observed_mode,
    parse_json_records,
    summarize_suite,
)


def test_parse_json_records_supports_json_array() -> None:
    rows, err = parse_json_records('[{"a":1},{"a":2}]')
    assert err == ""
    assert len(rows) == 2


def test_parse_json_records_supports_jsonl() -> None:
    rows, err = parse_json_records('{"a":1}\n{"a":2}')
    assert err == ""
    assert len(rows) == 2


def test_infer_observed_mode_detects_json() -> None:
    assert infer_observed_mode('{"instruction":"x"}') == "json_train"
    assert infer_observed_mode("这是调研报告。") == "report"


def test_evaluate_json_content_checks_count_and_fields() -> None:
    content = '{"instruction":"i1","input":"x","output":"y","category":"c"}\n' \
              '{"instruction":"i2","input":"x","output":"y","category":"c"}'
    result = evaluate_json_content(
        content=content,
        expected_count=2,
        required_fields=["instruction", "input", "output", "category"],
    )
    assert result["json_gate_pass"] is True


def test_evaluate_report_content_applies_gates_and_score() -> None:
    parts = [f"第{i}节：这是用于质量验证的调研段落，包含背景、方法、证据与结论。" for i in range(1, 35)]
    text = "".join(parts) + " 来源: https://example.com/a 来源: https://example.com/b "
    report_cfg = {
        "gates": {"min_char_count": 500, "min_citation_count": 1, "require_fluency_pass": True},
        "scoring": {
            "char_score_max": 60,
            "char_score_full_at": 1200,
            "citation_score_max": 40,
            "citation_score_full_at": 6,
        },
    }
    result = evaluate_report_content(content=text, task_results=[], report_cfg=report_cfg)
    assert result["report_gate_pass"] is True
    assert result["report_provisional_score"] > 0


def test_summarize_suite_outputs_rates() -> None:
    records = [
        {
            "classification_correct": True,
            "has_output": True,
            "report_gate_pass": True,
            "backend_latency_ms": 100,
            "token_used_once": 10,
            "parallel_agent_peak": 2,
        },
        {
            "classification_correct": False,
            "has_output": True,
            "json_gate_pass": True,
            "backend_latency_ms": 300,
            "token_used_once": 30,
            "parallel_agent_peak": 3,
        },
    ]
    out = summarize_suite(records)
    assert out["total"] == 2
    assert out["classification_accuracy"] == 0.5
    assert out["has_output_rate"] == 1.0
    assert out["parallel_peak_max"] == 3
