from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

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
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


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


_SYNONYM_MAP = {
    "领先": "优势",
    "强": "优势",
    "更强": "优势",
    "场景落地": "部署",
    "落地": "部署",
    "执行": "实施",
}


def _normalize_text(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = re.sub(r"[\s\t\r\n]+", " ", normalized)
    normalized = re.sub(r"[，。！？；：、,.!?;:\(\)\[\]{}\"'“”‘’]+", " ", normalized)
    for source, target in _SYNONYM_MAP.items():
        normalized = normalized.replace(source, target)
    return normalized.strip()


def _split_token_chunks(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())


def _expanded_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for chunk in _split_token_chunks(text):
        if not chunk:
            continue
        tokens.add(chunk)
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
            chars = list(chunk)
            tokens.update(chars)
            if len(chars) >= 2:
                tokens.update("".join(chars[i : i + 2]) for i in range(len(chars) - 1))
    return tokens


def _char_bigrams(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", _normalize_text(text))
    if len(compact) < 2:
        return {compact} if compact else set()
    return {compact[i : i + 2] for i in range(len(compact) - 1)}


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _split_claims(content: str) -> List[str]:
    claims = [part.strip() for part in re.split(r"[。！？.!?\n]", content) if part.strip()]
    return claims


def evaluate_correctness(content: str, evidence_list: List[str]) -> DimensionEvaluation:
    claims = _split_claims(content)
    if not claims:
        return DimensionEvaluation(score=1.0)

    evidence_tokens = [_tokens(item) for item in evidence_list]
    normalized_evidence_tokens = [_expanded_tokens(_normalize_text(item)) for item in evidence_list]
    evidence_bigrams = [_char_bigrams(item) for item in evidence_list]

    unsupported: List[str] = []
    matched_evidence: List[str] = []
    diagnostics: List[Dict[str, Any]] = []
    meaningful_claim_count = 0
    unsupported_missing = 0
    unsupported_mismatch = 0
    for claim in claims:
        claim_tokens = _tokens(claim)
        if not claim_tokens:
            continue
        if not any(not token.isdigit() for token in claim_tokens):
            continue
        meaningful_claim_count += 1

        matched_level = "none"
        matched_item = ""
        max_similarity = 0.0
        max_norm_overlap = 0

        # 1) lexical match
        for idx, token_set in enumerate(evidence_tokens):
            if claim_tokens & token_set:
                matched_level = "lexical_match"
                matched_item = evidence_list[idx]
                break

        # 2) normalized match
        if matched_level == "none":
            claim_norm_tokens = _expanded_tokens(_normalize_text(claim))
            for idx, norm_set in enumerate(normalized_evidence_tokens):
                overlap = len(claim_norm_tokens & norm_set)
                if overlap > max_norm_overlap:
                    max_norm_overlap = overlap
                if overlap >= 3:
                    matched_level = "normalized_match"
                    matched_item = evidence_list[idx]
                    break

        # 3) semantic-like match (character bigram similarity)
        if matched_level == "none":
            claim_bigrams = _char_bigrams(claim)
            best_idx = -1
            for idx, candidate_bigrams in enumerate(evidence_bigrams):
                similarity = _jaccard_similarity(claim_bigrams, candidate_bigrams)
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_idx = idx
            if max_similarity >= 0.28 and best_idx >= 0:
                matched_level = "semantic_match"
                matched_item = evidence_list[best_idx]

        if matched_level != "none":
            matched_evidence.append(claim)
            diagnostics.append(
                {
                    "claim": claim,
                    "label": "supported",
                    "match_level": matched_level,
                    "matched_evidence": matched_item,
                }
            )
            continue

        reason = "evidence_missing"
        if evidence_list and (max_norm_overlap > 0 or max_similarity >= 0.05):
            reason = "evidence_mismatch"

        unsupported.append(claim)
        if reason == "evidence_missing":
            unsupported_missing += 1
        else:
            unsupported_mismatch += 1
        diagnostics.append(
            {
                "claim": claim,
                "label": "unsupported",
                "match_level": "none",
                "failure_reason": reason,
            }
        )

    if meaningful_claim_count == 0:
        return DimensionEvaluation(score=1.0)

    base = 1.0 - (len(unsupported) / meaningful_claim_count)
    score = _clamp(base)
    findings = []
    for row in diagnostics:
        if row.get("label") == "unsupported":
            reason = str(row.get("failure_reason") or "evidence_missing")
            findings.append(f"unsupported_claim[{reason}]: {row.get('claim')}")

    unsupported_ratio = len(unsupported) / meaningful_claim_count
    pseudo_false_negative_ratio = unsupported_mismatch / meaningful_claim_count
    diagnostics.append(
        {
            "summary": {
                "claim_count": meaningful_claim_count,
                "unsupported_count": len(unsupported),
                "evidence_missing_count": unsupported_missing,
                "evidence_mismatch_count": unsupported_mismatch,
                "unsupported_ratio": unsupported_ratio,
                "pseudo_false_negative_ratio": pseudo_false_negative_ratio,
            }
        }
    )

    suggestions = ["为无证据结论补充可核查依据，或移除该结论。"] if unsupported else []
    return DimensionEvaluation(
        score=score,
        findings=findings,
        evidence=matched_evidence[:5],
        suggestions=suggestions,
        diagnostics=diagnostics,
    )


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
                "diagnostics": dim.diagnostics,
            }
            for name, dim in result.dimensions.items()
        },
        "final": {
            "total_score": result.total_score,
            "verdict": result.verdict,
            "summary": result.summary,
        },
    }