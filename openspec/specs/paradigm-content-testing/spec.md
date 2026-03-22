## ADDED Requirements

### Requirement: Dual Query Suite Execution
系统 MUST 支持按测试套件执行两类固定查询集：Set A（report，20条）与 Set B（json_train，5条）。

#### Scenario: Execute report suite
- **WHEN** 测试入口接收 suite_id=report_set_a
- **THEN** 系统按预置顺序执行20条报告查询并逐条记录结果

#### Scenario: Execute json suite
- **WHEN** 测试入口接收 suite_id=json_set_b
- **THEN** 系统按预置顺序执行5条JSON训练数据查询并逐条记录结果

### Requirement: Paradigm Classification Validation
系统 MUST 对每条查询记录 expected_mode 与 observed_mode，并输出 classification_correct 布尔结果。

#### Scenario: Mark classification correctness
- **WHEN** 单条查询执行完成并得到输出内容
- **THEN** 系统输出 expected_mode、observed_mode 与 classification_correct 字段

### Requirement: Backend Runtime Metrics Collection
系统 MUST 仅基于后端链路采集运行指标：has_output、backend_latency_ms、parallel_agent_peak、token_used_once。

#### Scenario: Capture backend-only metrics
- **WHEN** 单条查询在后端执行完成
- **THEN** 系统记录后端完整响应时延、并行调度峰值与单次token消耗，且不包含前端传输时延

### Requirement: Report Baseline Quality Gate
系统 MUST 对 report 模式执行内容底线校验：字数不少于500、存在合理引用、语言流畅性通过。

#### Scenario: Pass report baseline gate
- **WHEN** 输出为 report 且满足字数、引用、流畅性三项底线
- **THEN** 系统将 report_gate_pass 标记为 true

### Requirement: JSON Baseline Validation Gate
系统 MUST 对 json_train 模式执行结构校验，至少包含：可解析、条数匹配、字段完整、字段非空约束；该模式暂不计算评分。

#### Scenario: Validate JSON structure without scoring
- **WHEN** 输出为 json_train
- **THEN** 系统执行结构与字段校验并输出通过/失败，不输出质量评分

### Requirement: Unified Per-Query Result Schema
系统 MUST 使用统一结果结构持久化每条查询记录，至少包含分类结果、门槛结果与运行指标。

#### Scenario: Emit unified query record
- **WHEN** 任一查询执行结束
- **THEN** 系统写入统一结构记录，支持后续 suite 聚合统计
