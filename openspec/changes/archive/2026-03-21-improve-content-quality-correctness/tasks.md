## 1. Correctness Matching Upgrade

- [x] 1.1 抽离 claim/evidence 归一化处理流程（大小写、标点、数字与常见同义映射）
- [x] 1.2 在 correctness 评估中实现词面匹配 + 归一化匹配的分层判定
- [x] 1.3 增加最小语义近似匹配路径并实现分层短路逻辑

## 2. Correctness Diagnostics & Reporting

- [x] 2.1 扩展 correctness 输出结构，记录 claim、匹配层级、候选证据与最终标签
- [x] 2.2 将 unsupported_claim 细分为 evidence_missing/evidence_mismatch
- [x] 2.3 在报告中新增 correctness 失败分解统计字段

## 3. Calibration Dataset & Regression Metrics

- [x] 3.1 新增 correctness 校准样本集并覆盖同义改写、跨句归因、摘要归纳场景
- [x] 3.2 在 regression 模式中输出 unsupported_ratio 与 pseudo_false_negative_ratio
- [x] 3.3 在回归摘要中接入 calibration_drift 告警条件

## 4. Tests & Acceptance

- [x] 4.1 新增 correctness 单测，覆盖词面不一致但语义一致的通过场景
- [x] 4.2 新增失败分类单测，验证 evidence_missing/evidence_mismatch 分流
- [x] 4.3 运行 single/regression 验收并更新基线与结果文档
