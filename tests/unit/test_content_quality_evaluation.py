from __future__ import annotations

from pathlib import Path

from shannon.quality.config import load_quality_scoring_config
from shannon.quality.evaluation import (
    QualityEvaluationInput,
    evaluate_content_quality,
    generate_quality_report,
)


def test_correctness_and_completeness_pass_case():
    payload = QualityEvaluationInput(
        content="结论：dataset 字段需要校验。\n1. 检查 dataset\n2. 校验 field。",
        evidence=["dataset 字段需要校验", "field 是关键字段"],
        key_points=["dataset", "field"],
        task_goal="输出数据质量建议",
        target_user="analyst",
    )
    config = load_quality_scoring_config()

    result = evaluate_content_quality(payload, config)

    assert result.dimensions["correctness"].score >= 0.9
    assert result.dimensions["completeness"].score == 1.0
    assert result.verdict in {"passed", "warning"}


def test_correctness_passes_on_synonym_or_near_semantic_match():
    payload = QualityEvaluationInput(
        content="美国在基础模型生态更强，中国在产业部署效率更领先。",
        evidence=[
            "美国拥有头部基础模型公司与云生态优势",
            "中国在行业部署与工程化交付效率方面表现突出",
        ],
        key_points=["基础模型", "部署效率"],
    )
    config = load_quality_scoring_config()

    result = evaluate_content_quality(payload, config)

    assert result.dimensions["correctness"].score >= 0.5
    assert any(
        isinstance(item, dict) and item.get("label") == "supported"
        for item in result.dimensions["correctness"].diagnostics
    )


def test_correctness_and_completeness_fail_case():
    payload = QualityEvaluationInput(
        content="系统已经满足全部要求。并且无需任何输入。",
        evidence=[],
        key_points=["dataset", "field"],
    )
    config = load_quality_scoring_config()

    result = evaluate_content_quality(payload, config)

    assert result.dimensions["correctness"].score < 0.5
    assert result.dimensions["completeness"].score == 0.0
    assert result.verdict == "failed"


def test_correctness_failure_reason_split_between_missing_and_mismatch():
    payload = QualityEvaluationInput(
        content="政务升级需要评估。量子芯片突破明显。",
        evidence=["政策框架持续推进"],
        key_points=[],
    )
    config = load_quality_scoring_config()

    result = evaluate_content_quality(payload, config)
    findings = result.dimensions["correctness"].findings

    assert any("unsupported_claim[evidence_mismatch]" in item for item in findings)
    assert any("unsupported_claim[evidence_missing]" in item for item in findings)
    summary_rows = [
        item["summary"]
        for item in result.dimensions["correctness"].diagnostics
        if isinstance(item, dict) and isinstance(item.get("summary"), dict)
    ]
    assert summary_rows
    summary = summary_rows[0]
    assert "unsupported_ratio" in summary
    assert "pseudo_false_negative_ratio" in summary


def test_structure_and_usability_negative_samples():
    payload = QualityEvaluationInput(
        content=(
            "我们支持该方案但是我们不支持该方案因此需要讨论"
            "这个文本很长却没有清晰结构也没有步骤说明"
        ),
        evidence=["支持该方案"],
    )
    config = load_quality_scoring_config()

    result = evaluate_content_quality(payload, config)

    assert result.dimensions["structure"].score < 0.8
    assert result.dimensions["usability"].score < 0.8
    assert result.dimensions["structure"].findings


def test_report_verdict_consistency():
    payload = QualityEvaluationInput(
        content="1. 执行检查\n2. 输出建议",
        evidence=["执行检查", "输出建议"],
        key_points=["检查", "建议"],
    )
    config = load_quality_scoring_config()

    result = evaluate_content_quality(payload, config)
    report = generate_quality_report(payload, result)

    assert report["final"]["verdict"] == result.verdict
    assert report["final"]["total_score"] == result.total_score


def test_load_quality_config_from_custom_file(tmp_path: Path):
    path = tmp_path / "content_quality.yaml"
    path.write_text(
        """
weights:
  correctness: 0.4
  completeness: 0.2
  structure: 0.2
  usability: 0.2
thresholds:
  pass: 0.9
  warning: 0.7
  correctness_hard: 0.6
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_quality_scoring_config(path)

    assert cfg.correctness_weight == 0.4
    assert cfg.pass_threshold == 0.9
    assert cfg.correctness_hard_threshold == 0.6