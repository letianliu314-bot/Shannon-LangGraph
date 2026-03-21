## 1. Phase 1 - Memory Layer Foundation

- [x] 1.1 定义 `reports/<run_id>/` 目录规范与文件命名规则（含 task 产物与元数据）
- [x] 1.2 实现共享记忆读写接口契约（按 run_id/task_id/stage/capability 检索）
- [x] 1.3 实现依赖透传兜底路径并记录降级事件
- [x] 1.4 编写 Phase 1 验收脚本：目录隔离、跨 run 写保护、检索准确性
- [x] 1.5 执行 Phase 1 验收并出具通过结论（未通过不得进入 Phase 2）

## 2. Phase 2 - Orchestration Layer Integration

- [x] 2.1 在编排层接入共享记忆读取策略（共享记忆优先 + 依赖透传兜底）
- [x] 2.2 实现阶段门禁状态机（阶段进入条件、退出条件、失败冻结）
- [x] 2.3 补充运行态事件与日志字段（phase、gate_status、run_id）
- [x] 2.4 编写 Phase 2 验收脚本：门禁阻断、降级可用性、DAG 兼容性
- [x] 2.5 执行 Phase 2 验收并出具通过结论（未通过不得进入 Phase 3）

## 3. Phase 3 - Version Layer and Append-Only Governance

- [x] 3.1 实现 task 级 commit 强制策略（每个有效 task 产出必须提交）
- [x] 3.2 实现 stage 级 tag 策略（`stage/<run_id>/phase-N`）
- [x] 3.3 实现 append-only 守卫：禁止 rebase、禁止 merge
- [x] 3.4 为 commit 增加审计字段（run_id、task_id、stage、quality_score、decay_score）
- [x] 3.5 编写 Phase 3 验收脚本：提交粒度、tag 边界、违规拦截
- [x] 3.6 执行 Phase 3 验收并出具通过结论（未通过不得进入 Phase 4）

## 4. Phase 4 - Prompt Expert Service Rollout

- [x] 4.1 定义 Prompt Expert 接口协议（输入、输出、contract_version）
- [x] 4.2 在 llm_service 内挂载 Prompt Expert（保持逻辑独立边界）
- [x] 4.3 将子 Agent 身份与任务 prompt 生成链路切换至 Prompt Expert
- [x] 4.4 补充回退策略：Prompt Expert 不可用时的受控降级
- [x] 4.5 编写 Phase 4 验收脚本：契约稳定性、提示词完整性、回退行为
- [x] 4.6 执行 Phase 4 验收并出具通过结论（未通过不得进入 Phase 5）

## 5. Phase 5 - Quality-First + Time-Decay and E2E Acceptance

- [x] 5.1 实现质量优先 + 时间衰减排序函数（保证质量权重大于时间衰减权重）
- [x] 5.2 输出评分拆解字段（quality_score、decay_score、final_score）
- [x] 5.3 完成端到端联调：Memory/Orchestration/Version/Prompt Expert 全链路
- [x] 5.4 编写并执行 Phase 5 验收脚本：排序有效性、可解释性、全流程稳定性
- [x] 5.5 完成最终阶段验收与变更总结（通过后方可进入实施阶段）

## 6. Stage Gate Enforcement and Acceptance Ledger

- [x] 6.1 建立统一验收记录模板（阶段目标、测试结果、证据链接、审批结论）
- [x] 6.2 将每阶段验收结果写入 run 目录并执行 task 级 commit
- [x] 6.3 在阶段验收通过时打 stage tag，失败时冻结后续阶段入口
- [x] 6.4 对每次门禁决策产生日志审计条目（append-only）
