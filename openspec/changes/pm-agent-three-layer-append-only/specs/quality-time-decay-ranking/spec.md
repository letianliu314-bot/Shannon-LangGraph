## ADDED Requirements

### Requirement: Quality-First Ranking Policy
系统 MUST 将质量评分设为主排序因子，且其权重高于时间衰减因子。

#### Scenario: Higher quality outranks fresher low-quality item
- **WHEN** 两条候选记忆中一条质量更高但时间较早
- **THEN** 在默认策略下高质量条目优先于低质量新条目

### Requirement: Mandatory Time Decay Factor
系统 MUST 在默认排序中包含时间衰减因子，且该因子不可关闭。

#### Scenario: Stale item receives decay penalty
- **WHEN** 某条记忆显著陈旧
- **THEN** 系统对其施加时间衰减分并在最终排序中体现

### Requirement: Explainable Ranking Output
系统 MUST 返回排序结果的可解释字段，至少包含 quality_score、decay_score 与 final_score。

#### Scenario: Return scoring breakdown
- **WHEN** 下游任务请求共享记忆检索结果
- **THEN** 每条结果包含评分拆解字段用于审计和调试
