from __future__ import annotations

import os
from typing import Any, Dict

from shannon.llm_service.presets import get_preset

# 中文注释：Prompt Expert（逻辑独立，物理先挂载在 llm_service）

CONTRACT_VERSION = "v2"


def _is_integration_task(task: Dict[str, Any]) -> bool:
    task_id = str(task.get("id") or "").strip().lower()
    title = str(task.get("title") or "").strip().lower()
    goal = str(task.get("goal") or "").strip().lower()
    deliverable = str(task.get("deliverable") or "").strip().lower()
    text = " ".join([task_id, title, goal, deliverable])
    return "task-merge" in text or "cross-check" in text or "integration" in text


def _dynamic_role_identity(task: Dict[str, Any]) -> str:
    if _is_integration_task(task):
        return (
            "You are an Evidence Integration Auditor. Aggregate child outputs, normalize facts, "
            "resolve conflicts by source authority and recency, and produce a traceable integration brief."
        )

    goal = str(task.get("goal") or "").lower()
    deliverable = str(task.get("deliverable") or "").lower()
    if "jsonl" in deliverable or "structured" in deliverable:
        return (
            "You are a Structured Output Composer. Convert validated upstream evidence into strict schema-compliant output "
            "without introducing unsupported claims."
        )
    if any(token in goal for token in ["compare", "contrast", "difference", "对比", "比较"]):
        return (
            "You are a Comparative Analyst. Focus on consistent dimensions, explicit tradeoffs, "
            "and evidence-backed differences."
        )
    return (
        "You are an Evidence Scout. Gather high-value evidence within scope, answer key questions, "
        "and surface uncertainty when support is weak."
    )


def build_prompt_contract(
    *,
    role_preset: str,
    task: Dict[str, Any],
    user_request: str,
    refined: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if str(os.getenv("PROMPT_EXPERT_FORCE_FAIL", "false")).lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("prompt expert forced failure")

    preset = get_preset(role_preset)
    title = str(task.get("title") or "")
    goal = str(task.get("goal") or "")
    description = str(task.get("description") or "")
    acceptance = task.get("acceptance_criteria") if isinstance(task.get("acceptance_criteria"), list) else []

    role_prompt = (
        f"{str(preset.get('system_prompt') or '')}\n\n"
        f"Dynamic role identity: {_dynamic_role_identity(task)}"
    )
    task_prompt = (
        f"Task title: {title}\n"
        f"Task goal: {goal}\n"
        f"Task description: {description}\n"
        f"Acceptance criteria: {acceptance}\n"
        f"Original user request: {user_request}\n"
        f"Refined context: {refined or {}}"
    )

    constraints = [
        "Output must stay grounded in retrieved or dependency evidence",
        "Do not invent sources, citations, or certainty",
        "Respect task boundaries and required deliverable format",
        "For high-impact claims, provide claim-to-evidence traceability",
        "If evidence is insufficient or conflicting, explicitly label uncertainty",
        "If integration task, produce canonical_facts, claim_evidence_map, conflicts, uncertainties, and gap_ledger",
        "Validate contract completeness before execution: objective, boundaries, source_guidance, output_format, acceptance_criteria",
    ]

    return {
        "contract_version": CONTRACT_VERSION,
        "role_preset": role_preset,
        "role_prompt": role_prompt,
        "task_prompt": task_prompt,
        "constraints": constraints,
        "source": "prompt_expert",
    }
