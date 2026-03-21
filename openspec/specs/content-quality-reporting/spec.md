# Purpose

定义内容质量评测报告的结构化输出、可审计字段与结论表达规范。

## ADDED Requirements

### Requirement: Structured Quality Report Output
系统 MUST 为每次评测生成结构化报告，至少包含输入摘要、四维分数、最终结论与时间戳。

#### Scenario: Generate report after evaluation
- **WHEN** 一次内容质量评测完成
- **THEN** 系统输出结构化报告并写入报告存储路径

### Requirement: Dimension-Level Findings
系统 MUST 在报告中按维度列出问题项、证据片段与影响说明。

#### Scenario: Include evidence for findings
- **WHEN** 任一维度存在扣分项
- **THEN** 报告包含该扣分项的证据引用与影响描述

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
