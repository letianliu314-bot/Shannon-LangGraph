## MODIFIED Requirements

### Requirement: Prompt Expert Service Contract
系统 MUST 提供 Prompt Expert 接口，用于生成子 Agent 身份、任务提示词与输出约束，不允许编排层直接拼接硬编码角色文案。接口 MUST 支持按查询复杂度与任务目标动态生成 capability-based role identity，并在返回中包含可执行的任务契约约束（scope、source policy、evidence rules、output requirements）。

#### Scenario: Generate dynamic role and contract via expert
- **WHEN** 编排层准备下发 task 且已获得复杂度与任务上下文
- **THEN** 编排层调用 Prompt Expert 接口获取 role prompt、task prompt、约束模板，以及面向动态身份的契约化字段要求

### Requirement: Logical Service Independence
Prompt Expert MUST 在逻辑边界上独立于通用执行接口，拥有明确输入输出契约与版本号。该契约 MUST 支持 integration-aware 约束表达，以便主 Agent 在汇总前执行强制信息整合关卡。

#### Scenario: Versioned integration-aware prompt contract response
- **WHEN** 调用 Prompt Expert
- **THEN** 响应包含 contract_version、字段完整性校验结果，以及用于支持 Evidence Integration Gate 的约束信息

## ADDED Requirements

### Requirement: Prompt Expert SHALL Emit Traceability Constraints for High-Impact Claims
Prompt Expert MUST provide constraints that require claim-to-evidence traceability and explicit uncertainty marking for high-impact conclusions.

#### Scenario: Traceability constraints included in prompt contract
- **WHEN** Prompt Expert returns a contract for analysis or synthesis tasks
- **THEN** contract constraints SHALL require evidence mapping for major claims and SHALL require uncertainty labels when evidence is insufficient or conflicting
