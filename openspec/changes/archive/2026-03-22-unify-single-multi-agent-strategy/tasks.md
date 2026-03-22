## 1. Product Strategy Surface Simplification

- [x] 1.1 Remove `quick` and `standard` from desktop strategy selector and keep a single visible strategy entry.
- [x] 1.2 Update frontend run payload wiring to use unified strategy semantics without mode branching.
- [x] 1.3 Update UI copy/help text to reflect single-strategy behavior.

## 2. Backend Strategy Convergence and Compatibility

- [x] 2.1 Converge orchestrator strategy normalization to unified semantics and eliminate distinct quick/standard runtime behavior.
- [x] 2.2 Converge llm-service strategy normalization and query-type/complexity mapping to unified semantics.
- [x] 2.3 Add deprecated-alias observability for incoming `quick`/`standard` requests (log or metadata path).

## 3. Minimum Multi-Agent Topology Enforcement

- [x] 3.1 Enforce decomposition correction that guarantees at least two research tasks when request is eligible for research flow.
- [x] 3.2 Enforce presence of `task-merge` integration gate when multi-task plans are built.
- [x] 3.3 Enforce downstream synthesis/transform dependency on `task-merge` when present.

## 4. Verification and Regression Safety

- [x] 4.1 Update unit tests that currently assert quick/standard/deep semantics to assert unified strategy behavior.
- [x] 4.2 Add/adjust tests for minimum topology guarantees (`task-1`, `task-2`, `task-merge`) and dependency correctness.
- [x] 4.3 Add/adjust tests for alias compatibility and deprecation observability.

## 5. Baseline Re-run and Rollout Gate

- [x] 5.1 Re-run content-quality single and regression evaluations using current baseline workflow.
- [x] 5.2 Collect and compare cost/latency deltas (tokens, task count, completion time) versus previous baseline.
- [x] 5.3 Produce rollout decision note with pass/fail against quality and cost thresholds, including rollback trigger conditions.
