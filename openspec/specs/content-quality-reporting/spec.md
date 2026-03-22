# Purpose

定义内容质量评测报告的结构化输出、可审计字段与结论表达规范。

## ADDED Requirements

### Requirement: Structured Quality Report Output
系统 MUST 为每次评测生成结构化报告，至少包含输入摘要、四维分数、最终结论与时间戳；在范式内容测试中，系统 MUST 额外包含 expected_mode、observed_mode、classification_correct、has_output、backend_latency_ms、parallel_agent_peak、token_used_once。

#### Scenario: Generate report after evaluation
- **WHEN** 一次内容质量评测完成
- **THEN** 系统输出结构化报告并写入报告存储路径

#### Scenario: Generate report with classification and runtime fields
- **WHEN** 一次范式内容评测完成
- **THEN** 系统输出结构化报告并包含分类正确性与运行指标字段

### Requirement: Dimension-Level Findings
系统 MUST 在报告中按维度列出问题项、证据片段与影响说明。对于 correctness 维度，系统 MUST 输出 claim-evidence 对齐明细，包含匹配层级、候选证据、失败原因分类与最终 supported/unsupported 标签。对于 report 模式，系统 MUST 输出字数、引用数、流畅性底线判定与临时评分；对于 json_train 模式，系统 MUST 输出结构校验结果且不包含评分。

#### Scenario: Include evidence for findings
- **WHEN** 任一维度存在扣分项
- **THEN** 报告包含该扣分项的证据引用与影响描述

#### Scenario: Include correctness alignment diagnostics
- **WHEN** correctness 维度存在 unsupported_claim 或低分
- **THEN** 报告包含 claim-evidence 对齐细节与失败原因分类，供调试和审计

#### Scenario: Emit report-mode baseline findings
- **WHEN** 评测对象为 report 模式
- **THEN** 报告包含 report 底线判定细项与临时评分

#### Scenario: Emit JSON-mode validation findings
- **WHEN** 评测对象为 json_train 模式
- **THEN** 报告包含 JSON 结构校验明细且不输出评分

### Requirement: Correctness Failure Breakdown Reporting
系统 MUST 在报告中输出 correctness 失败分解统计，至少包含 unsupported 总数、evidence_missing 数量与 evidence_mismatch 数量。

#### Scenario: Publish correctness failure breakdown
- **WHEN** correctness 评测完成
- **THEN** 报告输出失败分解统计并可用于回归趋势比较

### Requirement: Actionable Improvement Suggestions
系统 MUST 为 warning 或 failed 结论提供可执行改进建议。

#### Scenario: Recommend remediation steps
- **WHEN** 最终结论为 warning 或 failed
- **THEN** 报告输出可执行的改进建议清单

### Requirement: Report Verdict Consistency
系统 MUST 保证报告中的最终结论与评测引擎输出一致。

#### Scenario: Keep verdict aligned
- **WHEN** 评测引擎输出最终结论
- **THEN** 报告中最终结论字段与其完全一致

### Requirement: Suite-Level Aggregated Reporting
系统 MUST 支持按 suite 输出聚合统计，至少包含分类准确率、门槛通过率、时延统计与 token 消耗统计。

#### Scenario: Generate suite summary
- **WHEN** 一个查询套件执行完成
- **THEN** 系统输出 suite 级汇总结果，可用于回归对比
