## Context

当前系统使用 LangGraph 进行 DAG 编排，任务执行链路已具备并发调度、依赖控制和结果汇总能力，但长期记忆和跨任务协作仍高度依赖上下文窗口。现有任务结果传递以依赖透传为主，无法提供统一可检索共享层，也缺乏基于版本历史的可审计通信机制。

本设计遵循以下硬约束：
- 单分支 + run 目录隔离作为主路径。
- task 级 commit 为必须，stage 级 tag 为辅助。
- Prompt Expert 逻辑独立服务，首阶段物理挂载在 llm_service。
- 排序策略采用质量优先，且必须包含时间衰减因子。
- 工作流版本治理全面 append-only，禁止 rebase 与 merge。

## Goals / Non-Goals

**Goals:**
- 在不改变 LangGraph DAG 主编排形态的前提下，引入三层架构：Memory Layer、Orchestration Layer、Version Layer。
- 将跨任务通信主通道迁移到外部共享仓库与记忆检索接口，缓解 context window 压力。
- 建立 task 级版本记录和 stage 级快照能力，支持 workflow 回放与审计。
- 建立 Prompt Expert 服务化能力，统一子 Agent 身份与任务 prompt 产出。
- 建立质量优先 + 时间衰减的可解释排序函数，并作为默认策略。
- 实施 Phase 1-5 阶段门禁，阶段验收不通过不得推进下一阶段。

**Non-Goals:**
- 不替换 LangGraph 或重写编排框架。
- 不在本变更中实现多分支协作模型。
- 不引入 rebase/merge 兼容路径。
- 不在首阶段将 Prompt Expert 拆分为独立物理部署单元。

## Decisions

### Decision 1: 三层架构边界固定
- Memory Layer：负责 run 目录读写、共享检索、记忆索引与引用关系。
- Orchestration Layer：负责 DAG 调度、任务状态机、阶段门禁推进。
- Version Layer：负责 commit/tag 策略、append-only 校验、审计日志生成。
- 理由：将“思考上下文”与“流程控制”解耦，降低任务复杂度传播。
- 备选方案：继续沿用任务结果透传并追加向量检索。放弃原因：审计弱、协作边界不清晰。

### Decision 2: 单分支 + run 目录隔离
- 在共享仓库中仅保留单分支，所有运行数据落于 `reports/<run_id>/...`。
- 每个 task 在对应 run 目录追加产物文件与结构化元数据。
- 理由：符合 append-only 与统一检索路径，避免跨分支对齐成本。
- 备选方案：每 run 一分支。放弃原因：分支管理负担高，审计汇总复杂。

### Decision 3: task 级 commit + stage 级 tag
- 每个 task 输出必须触发一次提交，commit message 与 trailer 必须包含 run_id、task_id、stage、quality_score、decay_score。
- 每个 stage 完成后打轻量 tag（例如 `stage/<run_id>/phase-2`）作为验收快照。
- 理由：保证最细粒度可追溯，并提供阶段性稳定回放点。
- 备选方案：按 stage 聚合提交。放弃原因：丢失 task 级证据链。

### Decision 3.1: 轻量 Git 选型
- 主实现采用 Git CLI（最小依赖、运维成熟、与现有仓库工具链兼容）。
- 适配层预留 Dulwich 作为可选后端（仅在需要 Python 内嵌纯库化时启用）。
- 理由：在 append-only 强约束下，Git CLI 可最快形成可审计主链路，且便于在 CI 与本地一致执行。
- 备选方案：直接以 Dulwich 作为主后端。放弃原因：生态与调试经验不如 Git CLI 成熟，首期风险更高。

### Decision 4: Prompt Expert 逻辑独立，物理先内嵌
- 定义独立 Prompt Expert 接口契约与服务边界。
- 首期在 llm_service 内部挂载该能力，后续可无缝拆分部署。
- 理由：先验证逻辑独立性，再进行基础设施拆分，降低首期风险。
- 备选方案：直接独立部署。放弃原因：一次性改动过大，联调成本高。

### Decision 5: 质量优先 + 时间衰减
- 默认排序函数形态：`score = w_q * quality_score + w_t * decay_score`，且 `w_q > w_t`。
- 时间衰减为必选项，不允许关闭；质量为主导项，不允许被时间项反超主导关系。
- 理由：在保证证据质量前提下控制陈旧信息占比。
- 备选方案：时间优先。放弃原因：会抬升低质量新内容。

### Decision 6: 全面 append-only 治理
- 禁止 rebase、禁止 merge。
- 所有修订通过新 commit 追加，冲突通过新路径追加版本文件（例如 `v3.md`）解决，不覆盖历史。
- 理由：审计链完整、可追责、可回放。
- 备选方案：允许 rebase 保持线性历史。放弃原因：会破坏可审计性。

### Decision 7: 阶段门禁是强约束
- 定义 Phase 1-5，每阶段设置进入条件、验收检查与退出条件。
- 只有当前阶段验收通过，编排层才允许推进下一阶段。
- 理由：控制风险扩散，保证演进可验证。
- 备选方案：并行推进多阶段。放弃原因：问题定位困难，回滚成本高。

## Risks / Trade-offs

- [提交频率高导致仓库膨胀] -> 通过 run 归档策略与 tag 快照压缩检索面，保留 append-only 历史。
- [共享记忆引入噪声污染] -> 引入质量优先排序、引用白名单和任务级证据约束。
- [单分支并发写冲突] -> 采用 run 目录隔离 + 文件级追加规则，冲突时新文件版本追加而非覆盖。
- [Prompt Expert 内嵌导致边界模糊] -> 强制接口契约与模块隔离，提前预留独立部署配置。
- [阶段门禁降低短期迭代速度] -> 用阶段验收模板与自动检查降低人工成本。

## Migration Plan

1. Phase 1：建立 Memory Layer 数据契约、run 目录规范、共享读取 API（不改变 DAG 流程）。
2. Phase 2：在 Orchestration Layer 引入共享记忆读取路径与门禁状态机。
3. Phase 3：落地 Version Layer（task commit、stage tag、append-only 守卫），并启用 Git CLI 主链路。
4. Phase 4：接入 Prompt Expert（先 llm_service 挂载），替换静态 role/task prompt 生成链路。
5. Phase 5：落地质量优先 + 时间衰减策略并完成端到端验收。
6. 每阶段执行验收脚本；未通过则冻结下一阶段入口。

Artifact 顺序（运行时产物顺序，append-only）：
1. 生成 run 清单：`reports/<run_id>/run_manifest.json`（记录阶段、策略、约束）。
2. 生成 task 草稿产物：`reports/<run_id>/<agent>/<task_id>/draft.md`。
3. 生成 task 正式产物与元数据：`final.md` + `meta.json`（含 quality_score 与 decay_score）。
4. 执行 task 级 commit（必须）：提交该 task 新增文件与审计 trailer。
5. 汇总 stage 验收产物：`reports/<run_id>/stages/phase-N/acceptance.md`。
6. 验收通过后打 stage 级 tag（辅助）：`stage/<run_id>/phase-N`。
7. 进入下一阶段，重复 2-6；禁止 rebase/merge，仅允许新增 commit 追加。

回滚策略：
- 阶段内失败只允许通过新增 commit 进行修复。
- 回退到上一个稳定 stage tag 作为运行基线，但不删除任何历史 commit。

## Open Questions

- stage tag 的命名与保留周期是否需要按租户区分。
- quality_score 的统一评估器是否由 Prompt Expert 返回还是由编排层独立计算。
- 时间衰减函数是否按能力域提供不同半衰期配置。
- append-only 守卫由 pre-commit hook、CI，还是两者同时执行。
