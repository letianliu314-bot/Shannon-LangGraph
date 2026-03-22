## 1. Baseline Freeze and Dataset Setup

- [x] 1.1 固化两套 query 基线文件（Set A: report 20条，Set B: json_train 5条）并添加版本标识
- [x] 1.2 将冻结指标与门槛定义写入测试配置常量（report/json_train 共用与差异项分离）
- [x] 1.3 为每条 query 建立 expected_mode 映射与唯一 query_id 规则

## 2. Test Asset Reorganization

- [x] 2.1 盘点现有 tests 目录并标注“稳定性脚本保留白名单”
- [x] 2.2 删除不涉及稳定性校验与两类范式内容校验的历史测试文件
- [x] 2.3 将保留的稳定性脚本迁移到独立分组并补充说明文档

## 3. JSON Training Data Validation Suite

- [x] 3.1 复用并整合既有 JSON/JSONL 结构校验逻辑（可解析、条数、字段完整、字段非空）
- [x] 3.2 接入 Set B（5条）批量执行入口并输出逐条校验结果
- [x] 3.3 明确 json_train 模式不评分，仅输出 pass/fail 与失败原因

## 4. Research Report Validation Suite

- [x] 4.1 实现 report 模式底线门槛：字数>=500、存在合理引用、语言流畅性通过
- [x] 4.2 实现 report 临时评分：基于字数分与引用分计算总分
- [x] 4.3 接入 Set A（20条）批量执行入口并输出逐条门槛与评分结果

## 5. Runtime Metrics Instrumentation (Backend Only)

- [x] 5.1 在后端执行链路采集 has_output 与 backend_latency_ms（排除前端传输）
- [x] 5.2 采集并输出并行 agent 调度峰值 parallel_agent_peak
- [x] 5.3 采集并输出单次 token 消耗 token_used_once（并标记 actual/estimated 来源）

## 6. Unified Reporting and Aggregation

- [x] 6.1 统一逐条结果 schema（分类、门槛、评分、运行指标）
- [x] 6.2 输出 suite 级汇总（分类准确率、门槛通过率、时延统计、token统计）
- [x] 6.3 生成总览报告并对比 report/json_train 两套结果

## 7. Verification and Exit Criteria

- [x] 7.1 运行保留稳定性脚本，确认未引入稳定性回归
- [x] 7.2 运行两套 query 内容测试并核对分类与门槛结果
- [x] 7.3 记录首轮基线结果（P50/P90时延、token均值/极值、通过率）并提交变更总结
