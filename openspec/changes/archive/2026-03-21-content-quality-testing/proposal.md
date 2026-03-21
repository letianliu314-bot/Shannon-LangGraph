## Why

当前系统已经具备多层架构与阶段验收能力，但对“结果内容本身是否可靠可用”缺乏标准化测试。现在需要建立一套可重复执行的内容质量测试框架，用于系统性评估信息正确性、完整性、结构质量与可用性，降低“看起来完成但实际不可用”的交付风险。

## What Changes

- 新增一套面向内容质量的测试能力，覆盖四个核心维度：
- 信息正确性：识别事实错误、幻觉与无依据结论。
- 信息完整性：检查关键要点覆盖率与遗漏项。
- 结构质量：评估逻辑链路、层次组织与可追踪性。
- 可用性：评估目标用户可执行性、可读性与决策支持价值。
- 定义统一评分规则与结果分级（通过/警告/失败），并输出可审计报告。
- 建立可复现的评测输入样本与基线结果，支持回归比较。
- 将内容质量评测接入现有 Phase 验收流程，作为质量门禁的补充信号。

## Capabilities

### New Capabilities
- `content-quality-evaluation`: 定义四维评测流程、评分规则与判定阈值。
- `content-quality-reporting`: 产出结构化评测报告（分维度得分、问题清单、改进建议、最终结论）。
- `content-quality-regression-baseline`: 管理评测样本集与基线结果，用于版本间回归对比。

### Modified Capabilities
- `phased-gated-delivery`: 在阶段门禁中增加内容质量测试结果的接入规则与放行条件。

## Impact

- Affected code:
- 可能新增内容评测脚本、评分器与报告生成模块（预计位于 `deploy/scripts/`、`tests/` 与 `reports/` 相关路径）。
- 可能扩展编排层 gate 校验逻辑与验收产物写入路径。
- Affected APIs:
- 可能新增或扩展内部评测触发/查询接口（如需自动化执行与展示）。
- Dependencies:
- 可能引入文本相似度、规则匹配或评测辅助库（待 design 阶段确定）。
- Systems:
- 与现有 Shared Memory、Phase Gatekeeper、Version Layer 的验收链路形成联动；不改变 append-only 治理原则。
