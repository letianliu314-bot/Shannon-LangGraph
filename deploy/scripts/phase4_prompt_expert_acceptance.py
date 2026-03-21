from __future__ import annotations

import os

from shannon.llm_service.main import TaskContract, _resolve_prompt_contract

# 中文注释：Phase 4 验收脚本
# 目的：验证 Prompt Expert 主路径与降级路径在编排入口处的行为一致性
# 覆盖点：正常返回 contract、强制失败 fallback、元信息状态标记


def run_checks() -> None:
    # 中文注释：构造最小 task contract，模拟编排阶段传入的任务上下文
    task = TaskContract(
        id="task-1",
        title="Research infra",
        goal="Collect infra evidence",
        description="Collect evidence",
        deliverable="summary",
    )

    # 中文注释：主路径应成功解析并返回可执行的 prompt contract
    contract, meta = _resolve_prompt_contract(task=task, user_request="analyze infra", refined={"query_type": "analysis"})
    assert meta["status"] == "ok"
    assert "contract_version" in contract
    assert contract.get("role_prompt")
    assert contract.get("task_prompt")

    # 中文注释：通过环境变量触发失败分支，验证 fallback 可用性与可观测性
    os.environ["PROMPT_EXPERT_FORCE_FAIL"] = "true"
    fallback_contract, fallback_meta = _resolve_prompt_contract(task=task, user_request="analyze infra", refined={})
    assert fallback_meta["status"] == "fallback"
    assert fallback_contract.get("source") == "preset_fallback"
    os.environ.pop("PROMPT_EXPERT_FORCE_FAIL", None)

    print("Phase 4 acceptance passed")


if __name__ == "__main__":
    run_checks()
