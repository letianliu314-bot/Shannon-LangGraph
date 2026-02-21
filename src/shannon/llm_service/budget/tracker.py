from dataclasses import dataclass

# 中文注释：Token/成本统计


@dataclass
class BudgetTracker:
    # 中文注释：累计 token 与成本
    token_used: int = 0
    cost_used: float = 0.0

    # 中文注释：函数 record 的入口
    def record(self, tokens: int, cost: float) -> None:
        # 中文注释：累加统计值
        self.token_used += tokens
        self.cost_used += cost
