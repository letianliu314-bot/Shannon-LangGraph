from shannon.llm_service.budget.tracker import BudgetTracker

# 中文注释：预算超限拦截


def is_budget_exceeded(tracker: BudgetTracker, max_token: int, max_cost: float) -> bool:
    # 中文注释：任一维度超限则返回 True
    return tracker.token_used > max_token or tracker.cost_used > max_cost
