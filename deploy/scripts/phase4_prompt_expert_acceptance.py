from __future__ import annotations

import os

from shannon.llm_service.main import TaskContract, _resolve_prompt_contract


def run_checks() -> None:
    task = TaskContract(
        id="task-1",
        title="Research infra",
        goal="Collect infra evidence",
        description="Collect evidence",
        deliverable="summary",
    )

    contract, meta = _resolve_prompt_contract(task=task, user_request="analyze infra", refined={"query_type": "analysis"})
    assert meta["status"] == "ok"
    assert "contract_version" in contract
    assert contract.get("role_prompt")
    assert contract.get("task_prompt")

    os.environ["PROMPT_EXPERT_FORCE_FAIL"] = "true"
    fallback_contract, fallback_meta = _resolve_prompt_contract(task=task, user_request="analyze infra", refined={})
    assert fallback_meta["status"] == "fallback"
    assert fallback_contract.get("source") == "preset_fallback"
    os.environ.pop("PROMPT_EXPERT_FORCE_FAIL", None)

    print("Phase 4 acceptance passed")


if __name__ == "__main__":
    run_checks()
