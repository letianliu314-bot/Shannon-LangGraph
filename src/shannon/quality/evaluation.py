from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List

from .config import QualityScoringConfig


@dataclass(frozen=True)
class QualityEvaluationInput:
    content: str
    evidence: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    task_goal: str = ""
    target_user: str = ""


@dataclass(frozen=True)
class DimensionEvaluation:
    score: float
    findings: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class QualityEvaluationResult:
    dimensions: Dict[str, DimensionEvaluation]
    total_score: float
    verdict: str
    timestamp: float
    summary: str


def _clamp(score: float) -> float:
    return max(0.0, min(1.0, score))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", text)}


def _split_claims(content: str) -> List[str]:
    claims = [part.strip() for part in re.split(r"[。！？.!?\n]", content) if part.strip()]
    return claims


def evaluate_correctness(content: str, evidence_list: List[str]) -> DimensionEvaluation:
    claims = _split_claims(content)
    if not claims:
        return DimensionEvaluation(score=1.0)

    evidence_tokens = set()
    for item in evidence_list:
        evidence_tokens |= _tokens(item)

    unsupported: List[str] = []
    matched_evidence: List[str] = []
    meaningful_claim_count = 0
    for claim in claims:
        claim_tokens = _tokens(claim)
        if not claim_tokens:
            continue
        if not any(not token.isdigit() for token in claim_tokens):
            continue
        meaningful_claim_count += 1
        if evidence_tokens and claim_tokens & evidence_tokens:
            matched_evidence.append(claim)
        else:
            unsupported.append(claim)

    if meaningful_claim_count == 0:
        return DimensionEvaluation(score=1.0)

    base = 1.0 - (len(unsupported) / meaningful_claim_count)
    score = _clamp(base)
    findings = [f"unsupported_claim: {item}" for item in unsupported]
    suggestions = ["为无证据结论补充可核查依据，或移除该结论。"] if unsupported else []
    return DimensionEvaluation(score=score, findings=findings, evidence=matched_evidence[:5], suggestions=suggestions)


def evaluate_completeness(content: str, key_points: List[str]) -> DimensionEvaluation:
    if not key_points:
        return DimensionEvaluation(score=1.0)

    content_lower = content.lower()
    missing = [point for point in key_points if point and point.lower() not in content_lower]
    covered = len(key_points) - len(missing)
    score = _clamp(covered / max(len(key_points), 1))
    findings = [f"missing_key_point: {item}" for item in missing]
    suggestions = ["补充缺失关键点，并与任务目标逐条对齐。"] if missing else []
    return DimensionEvaluation(score=score, findings=findings, evidence=[f"covered:{covered}/{len(key_points)}"], suggestions=suggestions)


def evaluate_structure_quality(content: str) -> DimensionEvaluation:
    findings: List[str] = []
    suggestions: List[str] = []
    score = 1.0

    paragraphs = [line.strip() for line in content.splitlines() if line.strip()]
    transitions = ["因此", "所以", "首先", "其次", "最后", "because", "therefore", "first", "then", "finally"]

    if len(paragraphs) <= 1 and len(content) > 180:
        score -= 0.2
        findings.append("structure_flat: 内容较长但缺少层次分段")

    has_transition = any(word in content for word in transitions)
    if len(_split_claims(content)) >= 3 and not has_transition:
        score -= 0.2
        findings.append("logic_link_weak: 缺少明显逻辑连接词")

    contradictory_pairs = [("支持", "不支持"), ("可以", "不可以"), ("推荐", "不推荐")]
    for a, b in contradictory_pairs:
        if a in content and b in content:
            score -= 0.4
            findings.append(f"possible_conflict: 同时出现{a}/{b}")
            break

    score = _clamp(score)
    if findings:
        suggestions.append("按结论-依据-行动的顺序重组内容，并增加衔接语。")
    return DimensionEvaluation(score=score, findings=findings, evidence=paragraphs[:3], suggestions=suggestions)


def evaluate_usability(content: str) -> DimensionEvaluation:
    findings: List[str] = []
    suggestions: List[str] = []

    has_steps = bool(re.search(r"(^|\n)\s*(\d+[\).]|[-*])\s+", content))
    action_keywords = ["步骤", "执行", "运行", "检查", "建议", "下一步", "action", "run", "check"]
    action_hits = sum(1 for keyword in action_keywords if keyword in content.lower())

    score = 0.5
    if has_steps:
        score += 0.3
    if action_hits >= 2:
        score += 0.2
    elif action_hits == 0:
        score -= 0.2
        findings.append("non_actionable: 缺少明确可执行步骤或建议")

    score = _clamp(score)
    if findings:
        suggestions.append("增加可执行步骤、输入条件与预期结果。")
    return DimensionEvaluation(score=score, findings=findings, evidence=[f"action_hits:{action_hits}", f"has_steps:{has_steps}"], suggestions=suggestions)


def _weighted_total(dimensions: Dict[str, DimensionEvaluation], config: QualityScoringConfig) -> float:
    total = (
        dimensions["correctness"].score * config.correctness_weight
        + dimensions["completeness"].score * config.completeness_weight
        + dimensions["structure"].score * config.structure_weight
        + dimensions["usability"].score * config.usability_weight
    )
    return _clamp(total)


def _verdict(total_score: float, correctness_score: float, config: QualityScoringConfig) -> str:
    if correctness_score < config.correctness_hard_threshold:
        return "failed"
    if total_score >= config.pass_threshold:
        return "passed"
    if total_score >= config.warning_threshold:
        return "warning"
    return "failed"


def evaluate_content_quality(payload: QualityEvaluationInput, config: QualityScoringConfig) -> QualityEvaluationResult:
    dimensions: Dict[str, DimensionEvaluation] = {
        "correctness": evaluate_correctness(payload.content, payload.evidence),
        "completeness": evaluate_completeness(payload.content, payload.key_points),
        "structure": evaluate_structure_quality(payload.content),
        "usability": evaluate_usability(payload.content),
    }
    total_score = _weighted_total(dimensions, config)
    verdict = _verdict(total_score, dimensions["correctness"].score, config)
    summary = (
        f"correctness={dimensions['correctness'].score:.2f}, "
        f"completeness={dimensions['completeness'].score:.2f}, "
        f"structure={dimensions['structure'].score:.2f}, "
        f"usability={dimensions['usability'].score:.2f}, "
        f"total={total_score:.2f}, verdict={verdict}"
    )
    return QualityEvaluationResult(
        dimensions=dimensions,
        total_score=total_score,
        verdict=verdict,
        timestamp=time.time(),
        summary=summary,
    )


def generate_quality_report(payload: QualityEvaluationInput, result: QualityEvaluationResult) -> Dict[str, object]:
    return {
        "input_summary": {
            "task_goal": payload.task_goal,
            "target_user": payload.target_user,
            "content_length": len(payload.content),
            "evidence_count": len(payload.evidence),
            "key_point_count": len(payload.key_points),
        },
        "timestamp": result.timestamp,
        "dimensions": {
            name: {
                "score": dim.score,
                "findings": dim.findings,
                "evidence": dim.evidence,
                "suggestions": dim.suggestions,
            }
            for name, dim in result.dimensions.items()
        },
        "final": {
            "total_score": result.total_score,
            "verdict": result.verdict,
            "summary": result.summary,
        },
    }