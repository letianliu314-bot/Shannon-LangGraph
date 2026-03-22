## Why

The current quick/standard/deep strategy surface increases product complexity and creates inconsistent execution semantics for a system that is fundamentally multi-agent. We need one clear strategy path that always enforces integration-before-synthesis, while preserving predictable quality and cost through measurable rollout gates.

## What Changes

- Remove `quick` and `standard` from product-facing strategy controls; expose a single strategy entry for runs.
- Treat `quick` and `standard` as deprecated backend aliases that map to the unified multi-agent strategy semantics.
- Enforce a minimum multi-agent decomposition threshold in orchestrator planning:
  - at least two research tasks (`task-1`, `task-2`), and
  - one mandatory integration gate task (`task-merge`).
- Enforce dependency semantics so downstream synthesis/transform tasks depend on `task-merge` when present.
- Add rollout acceptance gates requiring both content quality stability and bounded cost/latency deltas before full rollout.

## Capabilities

### New Capabilities
- `single-strategy-entry`: Product/API strategy unification rules, alias handling policy, and user-facing behavior under a single strategy surface.

### Modified Capabilities
- `dynamic-agent-prompt-orchestration`: Tighten decomposition and dependency requirements to mandate minimum multi-agent topology and integration gate precedence.

## Impact

- Affected code:
  - strategy parsing/normalization in orchestrator and llm service
  - decomposition correction and dependency enforcement in orchestrator graph
  - desktop strategy selector behavior
  - tests that assert quick/standard/deep semantics
- API/runtime behavior:
  - backend continues to accept legacy strategy values for compatibility, but semantics converge to a unified path
- Validation and operations:
  - requires baseline re-run for quality and cost/latency comparison before full rollout
