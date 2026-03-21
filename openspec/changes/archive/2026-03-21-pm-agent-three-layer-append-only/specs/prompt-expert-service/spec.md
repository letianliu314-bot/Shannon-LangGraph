## ADDED Requirements

### Requirement: Prompt Expert Service Contract
系统 MUST 提供 Prompt Expert 接口，用于生成子 Agent 身份、任务提示词与输出约束，不允许编排层直接拼接硬编码角色文案。

#### Scenario: Generate role and task prompt via expert
- **WHEN** 编排层准备下发 task
- **THEN** 编排层调用 Prompt Expert 接口获取 role prompt、task prompt 与约束模板

### Requirement: Logical Service Independence
Prompt Expert MUST 在逻辑边界上独立于通用执行接口，拥有明确输入输出契约与版本号。

#### Scenario: Versioned prompt contract response
- **WHEN** 调用 Prompt Expert
- **THEN** 响应包含 contract_version 与字段完整性校验结果

### Requirement: Phase-1 Physical Co-Location
系统 MUST 支持 Prompt Expert 在初期物理挂载于 llm_service，并可在后续迁移为独立部署而不改变上层调用契约。

#### Scenario: Co-located deployment compatibility
- **WHEN** Prompt Expert 作为 llm_service 内部模块运行
- **THEN** 编排层仍通过统一服务契约调用且无需修改业务参数结构
