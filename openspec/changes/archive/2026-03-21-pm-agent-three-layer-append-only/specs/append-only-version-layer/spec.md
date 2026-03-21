## ADDED Requirements

### Requirement: Task-Level Commit Mandate
系统 MUST 为每一个 task 成功产出创建一次独立 commit，不允许跳过 task 级提交。

#### Scenario: Commit per completed task
- **WHEN** 任一 task 状态变为已完成且产出有效
- **THEN** 系统生成一次 commit 并关联该 task 的产物与元数据

### Requirement: Stage-Level Tag Snapshot
系统 MUST 在每个阶段验收通过后创建 stage 级 tag 作为快照锚点。

#### Scenario: Create stage tag after gate pass
- **WHEN** 某阶段所有验收项通过
- **THEN** 系统创建 `stage/<run_id>/phase-<n>` tag 指向该阶段最后一次提交

### Requirement: Append-Only Governance
系统 MUST 禁止 rebase 与 merge，并仅允许通过新增 commit 追加变更。

#### Scenario: Reject rebase and merge operations
- **WHEN** 流程中检测到 rebase 或 merge 操作请求
- **THEN** 系统拒绝该操作并记录 append-only 违规事件

#### Scenario: Resolve conflict by appending new revision
- **WHEN** 出现同路径内容冲突
- **THEN** 系统通过新增版本文件或新增 commit 追加解决，不覆盖历史记录

### Requirement: Commit Audit Trailer
系统 MUST 在每次 task commit 中写入可机读审计字段。

#### Scenario: Commit includes audit fields
- **WHEN** 系统提交 task 产物
- **THEN** commit message 或 trailer 至少包含 run_id、task_id、stage、quality_score、decay_score
