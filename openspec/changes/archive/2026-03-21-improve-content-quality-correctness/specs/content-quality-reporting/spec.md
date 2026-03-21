## MODIFIED Requirements

### Requirement: Dimension-Level Findings
系统 MUST 在报告中按维度列出问题项、证据片段与影响说明。对于 correctness 维度，系统 MUST 输出 claim-evidence 对齐明细，包含匹配层级、候选证据、失败原因分类与最终 supported/unsupported 标签。

#### Scenario: Include evidence for findings
- **WHEN** 任一维度存在扣分项
- **THEN** 报告包含该扣分项的证据引用与影响描述

#### Scenario: Include correctness alignment diagnostics
- **WHEN** correctness 维度存在 unsupported_claim 或低分
- **THEN** 报告包含 claim-evidence 对齐细节与失败原因分类，供调试和审计

## ADDED Requirements

### Requirement: Correctness Failure Breakdown Reporting
系统 MUST 在报告中输出 correctness 失败分解统计，至少包含 unsupported 总数、evidence_missing 数量与 evidence_mismatch 数量。

#### Scenario: Publish correctness failure breakdown
- **WHEN** correctness 评测完成
- **THEN** 报告输出失败分解统计并可用于回归趋势比较
