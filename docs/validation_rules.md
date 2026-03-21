# 验证规则扩展

- 规则配置在 `config/validation`
- 可调整质量阈值与预算限制

## 内容质量评测执行

- 单次评测：`python deploy/scripts/content_quality_acceptance.py --mode single`
- 刷新基线：`python deploy/scripts/content_quality_acceptance.py --mode refresh-baseline`
- 回归对比：`python deploy/scripts/content_quality_acceptance.py --mode regression`

默认样本路径：`reports/content_quality/samples/v1/samples.json`
默认报告路径：`reports/content_quality/latest_report.json`
默认基线路径：`reports/content_quality/baseline/v1_baseline.json`

## 阈值调整

内容质量权重与阈值配置在 `config/validation/content_quality.yaml`：

- `weights.correctness/completeness/structure/usability`
- `thresholds.pass`
- `thresholds.warning`
- `thresholds.correctness_hard`

建议先调整 warning 阈值并观察一轮回归，再调整 hard threshold。

## 回滚策略

- 若评测策略异常，可临时改为 `--mode single` 仅产出报告，不执行回归阻断。
- 可将 `thresholds.correctness_hard` 下调到保守值，避免短期误阻断。
- 基线回滚可直接恢复 `reports/content_quality/baseline/v1_baseline.json` 的上一版本。
