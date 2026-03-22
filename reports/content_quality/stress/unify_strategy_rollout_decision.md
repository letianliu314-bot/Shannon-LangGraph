# Unify Strategy Rollout Decision

## Scope

- Change: `unify-single-multi-agent-strategy`
- Goal: hard-merge strategy semantics to unified multi-agent path and enforce integration gate behavior.

## Evidence Inputs

- Quality single run report: `reports/content_quality/stress/unify_strategy_single.json`
- Quality regression report: `reports/content_quality/stress/unify_strategy_regression.json`
- Cost/latency sample report: `reports/content_quality/stress/unify_strategy_cost_latency.json`

## Quality Gate Result

- Sample count: 20
- Regression count: 0
- Has regression: false
- Correctness metric drift:
  - unsupported_ratio baseline/current: 0.056666666666666664 / 0.056666666666666664
  - pseudo_false_negative_ratio baseline/current: 0.028333333333333332 / 0.028333333333333332
- Gate status: PASS

## Cost/Latency Snapshot

Two live runs were sampled against the same request under requested strategies `quick` and `deep` (both now unified semantics):

- quick requested:
  - elapsed_seconds: 57.248
  - completed_task_count: 1
  - used_token: 281
- deep requested:
  - elapsed_seconds: 62.285
  - completed_task_count: 1
  - used_token: 52

Interpretation:
- Runtime behavior converges to the same completion status (`completed`) for legacy alias and canonical strategy.
- Cost/latency variation exists at sample level and should be monitored with larger sample size before full production rollout.

## Decision

- Decision: CONDITIONAL GO
- Rationale:
  - Quality regression gate passes with zero detected regressions.
  - Legacy alias path is operationally compatible.
  - Cost/latency data is limited (n=2) and should be expanded in staged rollout.

## Rollback Triggers

Rollback or hold rollout if any condition is met:

1. `regression_summary.has_regression` becomes true on official regression dataset.
2. Correctness metric regressions appear in `metric_regressions`.
3. P95 latency exceeds pre-change baseline by agreed threshold for 3 consecutive batches.
4. Token usage exceeds agreed budget ceiling for 3 consecutive batches.

## Next Actions

1. Expand cost/latency sampling to at least 30 runs across mixed query complexity.
2. Confirm integration-gate observability (`task-merge` presence and dependency compliance) from events/state telemetry.
3. Proceed to archive only after staged monitoring window is clean.
