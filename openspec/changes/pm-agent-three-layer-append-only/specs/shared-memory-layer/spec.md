## ADDED Requirements

### Requirement: Single-Branch Run Directory Isolation
系统 MUST 在单分支仓库中为每次运行创建唯一 run 目录，并将该运行所有中间产物和报告写入该目录，禁止跨 run 覆盖写入。

#### Scenario: Create isolated run workspace
- **WHEN** 编排层启动一个新的 run
- **THEN** 系统在共享仓库下创建 `reports/<run_id>/` 并将后续写入限定在该路径

#### Scenario: Prevent cross-run overwrite
- **WHEN** 某 task 尝试写入其他 run 的目录
- **THEN** 系统拒绝写入并返回路径隔离错误

### Requirement: Shared Memory Read/Write Contract
系统 MUST 提供统一的外部记忆读写契约，支持按 run_id、task_id、stage、capability 检索与引用。

#### Scenario: Write task memory with metadata
- **WHEN** task 执行完成并产出报告
- **THEN** 系统写入报告正文与结构化元数据（至少包含 run_id、task_id、stage、timestamp）

#### Scenario: Retrieve shared memory for downstream task
- **WHEN** 下游 task 请求共享记忆
- **THEN** 系统返回符合过滤条件的记忆条目及其版本引用信息

### Requirement: Dependency Handoff Compatibility
系统 MUST 在共享记忆机制上线后保留依赖透传兜底能力，确保已存在 DAG 任务不因共享记忆不可用而中断。

#### Scenario: Shared memory unavailable fallback
- **WHEN** 共享记忆读路径暂时不可用
- **THEN** 编排层回退到依赖任务结果透传并记录降级事件
