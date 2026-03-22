## MODIFIED Requirements

### Requirement: Four-Dimension Quality Evaluation
系统 MUST 对每条待评测内容在正确性、完整性、结构质量、可用性四个维度分别计算分数，并在范式内容测试场景下追加模式化门槛判定：report 模式执行报告底线门槛，json_train 模式执行结构化门槛。

#### Scenario: Produce per-dimension scores and mode gate
- **WHEN** 评测任务接收一条待评测内容
- **THEN** 系统输出四个维度分数与对应说明，并输出与模式对应的门槛判定结果

### Requirement: Weighted Final Verdict
系统 MUST 依据可配置权重计算总分，并按阈值给出 passed、warning、failed 结论。对于范式内容测试，系统 MUST 同时输出模式门槛结果与临时评分：report 模式按字数/引用数计算临时分，json_train 模式不计算临时分。

#### Scenario: Produce report provisional score
- **WHEN** 待评测内容属于 report 模式
- **THEN** 系统输出基于字数与引用数的临时评分，并保留 passed、warning、failed 结论

#### Scenario: Skip JSON provisional score
- **WHEN** 待评测内容属于 json_train 模式
- **THEN** 系统不输出临时评分字段，仅输出结构校验门槛结果与最终结论

## ADDED Requirements

### Requirement: Runtime Evaluation Metrics
系统 MUST 在评测结果中记录运行指标：has_output、backend_latency_ms、parallel_agent_peak、token_used_once。

#### Scenario: Attach runtime metrics to evaluation result
- **WHEN** 单条查询评测完成
- **THEN** 评测结果包含运行指标字段并可参与后续统计
