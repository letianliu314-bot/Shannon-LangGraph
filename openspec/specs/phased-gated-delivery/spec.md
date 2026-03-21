# Purpose

定义五阶段顺序交付与门禁冻结机制，确保阶段性验收后再推进。

## ADDED Requirements

### Requirement: Five-Phase Sequential Delivery
系统 MUST 将重构实施划分为 Phase 1 至 Phase 5，按顺序推进，禁止跳阶段执行。

#### Scenario: Enforce phase sequence
- **WHEN** 项目尝试启动某阶段实施
- **THEN** 系统校验前置阶段均已通过，否则拒绝进入

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

### Requirement: Phase Acceptance Evidence
系统 MUST 为每个阶段保存验收证据并写入版本层记录。

#### Scenario: Record acceptance artifacts
- **WHEN** 阶段验收完成
- **THEN** 系统保存验收结果、证据链接与时间戳，并可通过 run_id 检索

### Requirement: Stage Tag After Acceptance
系统 MUST 在阶段验收通过后打对应 stage tag，作为阶段边界。

#### Scenario: Tag phase boundary
- **WHEN** Phase N 验收通过
- **THEN** 系统创建对应 `stage/<run_id>/phase-N` 标签并记录到审计日志
