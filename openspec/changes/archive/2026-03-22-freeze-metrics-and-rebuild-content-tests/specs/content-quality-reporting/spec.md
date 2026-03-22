## MODIFIED Requirements

### Requirement: Structured Quality Report Output
系统 MUST 为每次评测生成结构化报告，至少包含输入摘要、四维分数、最终结论与时间戳；在范式内容测试中，系统 MUST 额外包含 expected_mode、observed_mode、classification_correct、has_output、backend_latency_ms、parallel_agent_peak、token_used_once。

#### Scenario: Generate report with classification and runtime fields
- **WHEN** 一次范式内容评测完成
- **THEN** 系统输出结构化报告并包含分类正确性与运行指标字段

### Requirement: Dimension-Level Findings
系统 MUST 在报告中按维度列出问题项、证据片段与影响说明。对于 report 模式，系统 MUST 输出字数、引用数、流畅性底线判定与临时评分；对于 json_train 模式，系统 MUST 输出结构校验结果且不包含评分。

#### Scenario: Emit report-mode baseline findings
- **WHEN** 评测对象为 report 模式
- **THEN** 报告包含 report 底线判定细项与临时评分

#### Scenario: Emit JSON-mode validation findings
- **WHEN** 评测对象为 json_train 模式
- **THEN** 报告包含 JSON 结构校验明细且不输出评分

## ADDED Requirements

### Requirement: Suite-Level Aggregated Reporting
系统 MUST 支持按 suite 输出聚合统计，至少包含分类准确率、门槛通过率、时延统计与 token 消耗统计。

#### Scenario: Generate suite summary
- **WHEN** 一个查询套件执行完成
- **THEN** 系统输出 suite 级汇总结果，可用于回归对比
