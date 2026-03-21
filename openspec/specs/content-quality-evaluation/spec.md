# Purpose

定义内容质量评测引擎在正确性、完整性、结构质量、可用性四个维度上的规范行为与统一判定标准。

## ADDED Requirements

### Requirement: Four-Dimension Quality Evaluation
系统 MUST 对每条待评测内容在正确性、完整性、结构质量、可用性四个维度分别计算分数。

#### Scenario: Produce per-dimension scores
- **WHEN** 评测任务接收一条待评测内容
- **THEN** 系统输出四个维度的独立分数与对应说明

### Requirement: Evidence-Backed Correctness Validation
系统 MUST 对正确性维度提供可核查证据，并标记无证据结论为风险项。

#### Scenario: Flag unsupported claims
- **WHEN** 输出内容包含无法由输入证据支持的结论
- **THEN** 系统记录该结论为正确性风险并降低正确性分数

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
系统 MUST 依据可配置权重计算总分，并按阈值给出 passed、warning、failed 结论。

#### Scenario: Fail on low correctness threshold
- **WHEN** 正确性分数低于硬性阈值
- **THEN** 系统将最终结论标记为 failed
