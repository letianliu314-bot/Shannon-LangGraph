# Purpose

扩展阶段门禁规范，使内容质量评测结果成为阶段放行决策的一部分。

## MODIFIED Requirements

### Requirement: Gate-Pass Before Next Phase
系统 MUST 在每个阶段结束时执行验收检查，未通过则冻结下一阶段入口。系统 MUST 将内容质量评测结论纳入放行判定：当结论为 failed 时阻断下一阶段；当结论为 warning 时按策略记录风险并可受控放行。

#### Scenario: Block progression on failed acceptance
- **WHEN** 当前阶段存在未通过验收项
- **THEN** 系统将阶段状态标记为 failed 并阻止下一阶段开始

#### Scenario: Block progression on failed content quality
- **WHEN** 当前阶段内容质量评测结论为 failed
- **THEN** 系统拒绝下一阶段进入并记录质量阻断原因

#### Scenario: Controlled pass with quality warning
- **WHEN** 当前阶段内容质量评测结论为 warning 且满足策略允许条件
- **THEN** 系统记录风险项并允许受控进入下一阶段
