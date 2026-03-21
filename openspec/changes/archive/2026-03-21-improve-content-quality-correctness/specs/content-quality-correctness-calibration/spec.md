## ADDED Requirements

### Requirement: Correctness Calibration Dataset
系统 MUST 维护 correctness 校准样本集，覆盖同义改写、跨句归因、摘要归纳三类场景，并支持按版本追踪样本变更。

#### Scenario: Track calibration dataset version
- **WHEN** 校准样本新增、删除或修改
- **THEN** 系统记录样本版本、变更说明与影响场景

### Requirement: Correctness Regression Metrics
系统 MUST 在回归结果中输出 correctness 相关核心指标，至少包含 unsupported_ratio 与 pseudo_false_negative_ratio。

#### Scenario: Emit correctness regression metrics
- **WHEN** 执行 regression 模式评测
- **THEN** 系统输出 correctness 核心指标并与基线进行对比

### Requirement: Calibration Gate Alert
系统 MUST 在 correctness 指标超过阈值时生成告警，提示存在误判上升风险。

#### Scenario: Alert on calibration drift
- **WHEN** unsupported_ratio 或 pseudo_false_negative_ratio 超过配置阈值
- **THEN** 系统生成 calibration_drift 告警并写入回归摘要
