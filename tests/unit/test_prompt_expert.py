from __future__ import annotations

import os

from shannon.llm_service.main import TaskContract, _resolve_prompt_contract
from shannon.llm_service.prompt_expert.service import build_prompt_contract


def test_prompt_expert_contract_fields():
    contract = build_prompt_contract(
        role_preset="deep_research_agent",
        task={"title": "t", "goal": "g", "description": "d", "acceptance_criteria": ["a"]},
        user_request="u",
        refined={"k": "v"},
    )
    assert contract["contract_version"] == "v1"
    assert contract["role_prompt"]
    assert contract["task_prompt"]


def test_prompt_expert_fallback_path():
    task = TaskContract(id="task-1", title="t", goal="g", description="d", deliverable="summary")

    os.environ["PROMPT_EXPERT_FORCE_FAIL"] = "true"
    contract, meta = _resolve_prompt_contract(task=task, user_request="u", refined={})
    os.environ.pop("PROMPT_EXPERT_FORCE_FAIL", None)

    assert meta["status"] == "fallback"
    assert contract["source"] == "preset_fallback"
