## Why

当前编排链路主要依赖上下文窗口和任务间定向透传，随着任务深度、并发数和多阶段协作增加，出现上下文过长、跨阶段记忆不可审计、任务产出难以版本化追踪的问题。现在需要将长上下文压力从模型窗口迁移到外部存储，并把 Agent 协作过程升级为可追溯、可回放、可验收的工程化流水线。

本变更在保持 LangGraph DAG 编排思路不变的前提下，重构为 Memory Layer + Orchestration Layer + Version Layer 三层架构，并采用 append-only 工作流约束，确保每个 task 的结果都能通过 commit 与目录产物被审计和复用。

## What Changes

- 新增 Memory Layer（外部记忆层）：采用单分支仓库与 run 目录隔离作为共享通信主路径，替代子 Agent 间严格数据隔离。
- 新增 Version Layer（版本层）：强制 task 级 commit，提供 stage 级 tag，形成 workflow 记录与可回溯历史。
- 新增 append-only 协议：禁止 rebase、禁止 merge，仅允许追加写入与提交。
- 新增 Prompt Expert 服务能力：逻辑上独立服务，负责子 Agent 身份与任务 prompt 生成；物理部署第一阶段先挂载到 llm_service。
- 在执行与检索策略中引入“质量优先 + 时间衰减”排序机制，保证新鲜度约束存在但不压制质量。
- 交付流程采用 Phase 1-5 阶段门禁，任何阶段未通过验收不得进入下一阶段。

## Capabilities

### New Capabilities
- `shared-memory-layer`: 定义单分支 + run 目录隔离的共享外部记忆读写、检索、引用与权限边界。
- `append-only-version-layer`: 定义 task 级 commit、stage 级 tag、append-only 约束及提交审计字段。
- `prompt-expert-service`: 定义独立 Prompt Expert 的输入输出契约与在 llm_service 挂载的过渡方案。
- `quality-time-decay-ranking`: 定义质量优先主排序与时间衰减必选因子，覆盖检索与记忆复用决策。
- `phased-gated-delivery`: 定义 Phase 1-5 的阶段门禁、验收规则和推进条件。

### Modified Capabilities
- （无）

## Impact

- 编排层：任务上下文装配与任务间结果传递策略将从“仅依赖透传”升级为“共享记忆优先 + 依赖透传兜底”。
- LLM Service：新增 Prompt Expert API 与排序策略接口，逐步承载独立服务能力。
- 存储与版本：引入共享仓库目录约定（run 级隔离）与提交日志审计字段，形成外部记忆与工作流记录主链路。
- 运维与流程：新增 append-only 治理规则（无 rebase、无 merge）与 stage tag 规范。
- 测试与验收：新增阶段门禁测试套件，要求按 Phase 1-5 顺序通过。
