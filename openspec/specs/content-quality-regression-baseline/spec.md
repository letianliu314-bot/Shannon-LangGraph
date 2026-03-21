# Purpose

定义内容质量回归基线的样本管理、版本对比与回退检测规则。

## ADDED Requirements

### Requirement: Baseline Dataset Management
系统 MUST 维护可复现的评测样本集，并支持按版本追踪样本变更。

#### Scenario: Track dataset changes
- **WHEN** 评测样本集新增或修改
- **THEN** 系统记录样本版本与变更说明

### Requirement: Baseline Score Persistence
系统 MUST 为每个样本保存基线分数与维度明细，用于后续回归比较。

#### Scenario: Persist baseline scores
- **WHEN** 首次建立基线或更新基线
- **THEN** 系统保存样本级总分与四维分数

### Requirement: Regression Detection
系统 MUST 对比当前评测结果与基线，检测显著质量回退。

#### Scenario: Detect score regression
- **WHEN** 当前结果低于基线且超出可接受波动阈值
- **THEN** 系统标记为回归并写入回归告警

### Requirement: Regression Summary Reporting
系统 MUST 输出回归摘要，包括回退维度、影响样本与严重度分级。

#### Scenario: Publish regression summary
- **WHEN** 一次回归对比执行完成
- **THEN** 系统生成回归摘要报告供门禁与人工复核使用
