## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Correctness Diagnostic Traceability
系统 MUST 为正确性评测输出可审计诊断信息，至少包含 claim 文本、候选证据片段、匹配层级、最终标签与失败原因。

#### Scenario: Emit claim-level diagnostics
- **WHEN** 一次评测完成
- **THEN** 系统在正确性维度输出 claim-level 对齐明细，支持人工复核
