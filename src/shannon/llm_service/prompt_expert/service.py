from __future__ import annotations

import os
from typing import Any, Dict

from shannon.llm_service.presets import get_preset

# 中文注释：Prompt Expert（逻辑独立，物理先挂载在 llm_service）

CONTRACT_VERSION = "v1"


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

    role_prompt = str(preset.get("system_prompt") or "")
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
        "Do not invent sources or citations",
        "Respect task boundaries and required deliverable format",
    ]

    return {
        "contract_version": CONTRACT_VERSION,
        "role_preset": role_preset,
        "role_prompt": role_prompt,
        "task_prompt": task_prompt,
        "constraints": constraints,
        "source": "prompt_expert",
    }
