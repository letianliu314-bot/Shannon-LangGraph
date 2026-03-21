## Why

当前内容质量评测在 correctness 维度依赖词面交集判定，导致语义一致但表述不同的结论被大量误判为 unsupported_claim，并触发 correctness_hard 门槛直接失败。这会放大假阴性，降低评测结果对真实质量的区分能力，因此需要尽快改进证据对齐与正确性打分策略。

## What Changes

- 将 correctness 的证据匹配从“纯词面交集”升级为“词面+归一化+最小语义近似”的分层判定。
- 增强证据诊断输出，区分“证据缺失”和“证据表达不一致”两类原因，减少不可解释失败。
- 引入 correctness 评测校准样本，覆盖同义改写、跨句归因、长段落结论等典型场景。
- 在报告中新增 correctness 调试信息字段，便于定位每条 claim 的命中依据。

## Capabilities

### New Capabilities
- `content-quality-correctness-calibration`: 定义 correctness 校准样本、回归评测规则与误判监控指标。

### Modified Capabilities
- `content-quality-evaluation`: 修改 correctness 维度的证据匹配与 unsupported_claim 判定规则。
- `content-quality-reporting`: 扩展 correctness 诊断字段，输出 claim-evidence 对齐细节与失败原因分类。

## Impact

- Affected code: `src/shannon/quality/evaluation.py`, `src/shannon/quality/regression.py`, `deploy/scripts/content_quality_acceptance.py`.
- Affected reports: `reports/content_quality/latest_report.json` 的 correctness 结构将增加诊断细节字段。
- Affected tests: 新增/更新 correctness 单测与回归样本测试，重点覆盖语义一致但词面不一致场景。
- Dependencies: 保持现有依赖，优先使用轻量规则与本地可复现策略，不引入重量级在线服务。
