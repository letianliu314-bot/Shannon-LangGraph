# Purpose

定义内容质量评测引擎在正确性、完整性、结构质量、可用性四个维度上的规范行为与统一判定标准。

## ADDED Requirements

### Requirement: Four-Dimension Quality Evaluation
系统 MUST 对每条待评测内容在正确性、完整性、结构质量、可用性四个维度分别计算分数，并在范式内容测试场景下追加模式化门槛判定：report 模式执行报告底线门槛，json_train 模式执行结构化门槛。

#### Scenario: Produce per-dimension scores
- **WHEN** 评测任务接收一条待评测内容
- **THEN** 系统输出四个维度的独立分数与对应说明

#### Scenario: Produce per-dimension scores and mode gate
- **WHEN** 评测任务接收一条待评测内容
- **THEN** 系统输出四个维度分数与对应说明，并输出与模式对应的门槛判定结果

### Requirement: Evidence-Backed Correctness Validation
系统 MUST 对正确性维度提供可核查证据，并标记无证据结论为风险项。系统 MUST 采用分层证据对齐策略（词面匹配、归一化匹配、最小语义近似匹配）判断 claim 是否被支持，并为每条 claim 输出匹配层级与失败原因分类。

#### Scenario: Flag unsupported claims
- **WHEN** 输出内容包含无法由输入证据支持的结论
- **THEN** 系统记录该结论为正确性风险并降低正确性分数

#### Scenario: Support claim via normalized matching
- **WHEN** claim 与 evidence 词面不完全一致但经归一化规则可对齐
- **THEN** 系统将该 claim 标记为 supported，并记录匹配层级为 normalized_match

#### Scenario: Classify unsupported reason
- **WHEN** claim 在所有匹配层级均未命中
- **THEN** 系统将失败原因标记为 evidence_missing 或 evidence_mismatch，并写入诊断明细

### Requirement: Correctness Diagnostic Traceability
系统 MUST 为正确性评测输出可审计诊断信息，至少包含 claim 文本、候选证据片段、匹配层级、最终标签与失败原因。

#### Scenario: Emit claim-level diagnostics
- **WHEN** 一次评测完成
- **THEN** 系统在正确性维度输出 claim-level 对齐明细，支持人工复核

### Requirement: Key-Point Completeness Coverage
系统 MUST 基于任务目标与关键点清单计算完整性覆盖率。

#### Scenario: Detect missing critical points
- **WHEN** 待评测内容缺少关键点清单中的一项或多项
- **THEN** 系统将缺失项写入问题列表并降低完整性分数

### Requirement: Structural Logic Assessment
系统 MUST 评估内容结构层次与逻辑连贯性，并输出结构问题说明。

#### Scenario: Identify structural inconsistency
- **WHEN** 内容出现前后结论冲突或论证链断裂
- **THEN** 系统记录结构质量问题并降低结构质量分数

### Requirement: Actionable Usability Assessment
系统 MUST 评估内容对目标用户的可执行性与可操作程度。

#### Scenario: Penalize non-actionable output
- **WHEN** 内容缺少可执行步骤或决策建议
- **THEN** 系统记录可用性不足并降低可用性分数

### Requirement: Weighted Final Verdict
系统 MUST 依据可配置权重计算总分，并按阈值给出 passed、warning、failed 结论。对于范式内容测试，系统 MUST 同时输出模式门槛结果与临时评分：report 模式按字数/引用数计算临时分，json_train 模式不计算临时分。

#### Scenario: Fail on low correctness threshold
- **WHEN** 正确性分数低于硬性阈值
- **THEN** 系统将最终结论标记为 failed

#### Scenario: Produce report provisional score
- **WHEN** 待评测内容属于 report 模式
- **THEN** 系统输出基于字数与引用数的临时评分，并保留 passed、warning、failed 结论

#### Scenario: Skip JSON provisional score
- **WHEN** 待评测内容属于 json_train 模式
- **THEN** 系统不输出临时评分字段，仅输出结构校验门槛结果与最终结论

### Requirement: Runtime Evaluation Metrics
系统 MUST 在评测结果中记录运行指标：has_output、backend_latency_ms、parallel_agent_peak、token_used_once。

#### Scenario: Attach runtime metrics to evaluation result
- **WHEN** 单条查询评测完成
- **THEN** 评测结果包含运行指标字段并可参与后续统计
