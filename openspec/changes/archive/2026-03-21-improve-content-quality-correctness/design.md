## Context

当前 correctness 判定对证据匹配采用纯词面交集，导致“语义一致但词面不同”的常见表达被误判 unsupported_claim。该问题在长文本、概括性结论、同义改写场景中尤为明显，并会触发 correctness_hard 门槛将最终结论直接判为 failed。现有评测链路已稳定接入样本、基线与回归，需要在不引入重型外部依赖的前提下提升 correctness 的稳健性与可解释性。

## Goals / Non-Goals

**Goals:**
- 将 correctness 从单一词面交集升级为分层匹配流程，降低假阴性。
- 在报告中输出 claim-evidence 对齐细节与失败分类，提升可诊断性。
- 通过校准样本与回归指标监控误判率，确保改动可持续验证。

**Non-Goals:**
- 不引入在线检索服务或重量级模型推理作为强依赖。
- 不改变 completeness、structure、usability 的基础评分定义。
- 不在本次变更中重构整套门禁策略，仅聚焦 correctness 质量提升。

## Decisions

### 1. 分层 correctness 匹配策略
- 决策：采用“词面匹配 -> 归一化匹配 -> 最小语义近似匹配”的三级流程，任一层命中即视为 supported。
- 原因：兼顾可解释性、实现复杂度和离线可复现性。
- 备选：
- 仅保留词面匹配。未选，误判率高。
- 直接采用重型语义模型。未选，成本高且可复现性弱。

### 2. 引入失败原因分类
- 决策：将 unsupported_claim 细分为 evidence_missing 与 evidence_mismatch 两类，并保留 claim 与命中证据片段。
- 原因：把“没有证据”与“证据存在但表达不一致”分开，便于调参与样本治理。
- 备选：维持单一 unsupported_claim。未选，问题定位粒度不足。

### 3. 报告增加 correctness 调试字段
- 决策：在 correctness 维度输出 claim 列表、匹配层级、候选证据与最终判定标签。
- 原因：支持人工复核与回归分析，减少“只看分数无法复现”的问题。
- 备选：仅输出总分。未选，调试价值不足。

### 4. 建立 correctness 校准样本与回归指标
- 决策：新增专用 capability 管理校准样本，覆盖同义改写、跨句归因、摘要归纳三类高风险场景；回归报告增加 correctness_fp_like_rate 与 unsupported_ratio。
- 原因：将一次性修复转为持续校准机制。
- 备选：仅用现有样本。未选，覆盖不足。

## Risks / Trade-offs

- [风险] 规则复杂度提升导致性能下降 -> 缓解：分层短路，先跑低成本规则，再进入近似匹配。
- [风险] 近似匹配过宽造成假阳性 -> 缓解：设置最小匹配阈值并保留人工可审计轨迹。
- [风险] 样本偏置导致过拟合 -> 缓解：按场景类型分桶抽样，回归时分别观察指标。

## Migration Plan

1. 先扩展 spec 与报告字段定义，保持向后兼容。
2. 实现 correctness 分层匹配与失败分类，保留旧字段以便对照。
3. 增加校准样本与回归指标，先在 single/regression 脚本中观测。
4. 通过一轮 baseline refresh 后切换到新基线。

回滚策略：
- 通过配置开关退回到词面匹配路径。
- 保留旧报告字段，必要时按旧逻辑重算并恢复旧 baseline。

## Open Questions

- 最小语义近似匹配采用何种轻量实现最稳妥（编辑距离、词向量、规则词典）？
- claim 与 evidence 的切分粒度是否需要按中文标点和段落类型进一步优化？
- correctness_hard 阈值是否需要按任务类型分层配置？
