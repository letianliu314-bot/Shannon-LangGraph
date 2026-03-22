## Context

The system currently exposes `quick`, `standard`, and `deep` as strategy options, but orchestration executes through one DAG with behavior differences mostly concentrated in planning and model-tier routing. This mismatch increases product cognitive load and leads to inconsistent expectations around multi-agent decomposition and integration-gate visibility. The new direction is to hard-merge strategy semantics into one product-facing path while preserving rollout safety with quality and cost gates.

## Goals / Non-Goals

**Goals:**
- Provide a single strategy entry in product surfaces and standard run requests.
- Converge backend strategy semantics to one multi-agent behavior model.
- Enforce minimum decomposition topology: at least two research tasks plus `task-merge`.
- Enforce integration-first dependencies for synthesis/transform tasks.
- Gate rollout on objective quality and cost/latency checkpoints.

**Non-Goals:**
- Introducing a new model provider or changing provider contracts.
- Redesigning orchestration graph topology beyond strategy/decomposition semantics.
- Adding new persisted schema fields for integration output typing in this phase.

## Decisions

1. Single product-facing strategy (hard merge)
- Decision: remove `quick`/`standard` from UI and user-facing semantics.
- Rationale: aligns product mental model with multi-agent architecture and avoids mode confusion.
- Alternatives considered:
  - Keep three strategies and tune prompts only: rejected due to persistent product complexity.
  - Keep hidden advanced modes in UI: rejected for now to prevent semantic drift.

2. Backend alias compatibility during transition
- Decision: treat `quick`/`standard` as deprecated aliases mapped to unified semantics.
- Rationale: avoids immediate breaking behavior for existing clients while removing distinct runtime meaning.
- Alternatives considered:
  - Immediate hard 4xx on legacy values: rejected due to migration risk.
  - Long-term dual semantics: rejected because it undermines hard-merge objective.

3. Minimum multi-agent threshold enforcement
- Decision: decompose correction guarantees at least two research tasks and one `task-merge` integration task.
- Rationale: ensures integration-gate behavior is observable and stable across runs.
- Alternatives considered:
  - Best-effort merge insertion only: rejected as insufficiently deterministic.
  - Always force 3+ research tasks: rejected due to unnecessary latency/cost for simple requests.

4. Integration dependency precedence
- Decision: synthesis/transform tasks must depend on `task-merge` when present, and final synthesis prioritizes integration artifact.
- Rationale: prevents direct raw-output synthesis and improves claim-evidence traceability.
- Alternatives considered:
  - Allow mixed dependency paths: rejected because it weakens gate semantics.

5. Staged rollout with quantitative guardrails
- Decision: release progression depends on quality non-regression and bounded cost/latency deltas.
- Rationale: hard-merge may improve output utility but can increase runtime cost; explicit gates control risk.
- Alternatives considered:
  - Ship directly without baselines: rejected due to unpredictable operational impact.

## Risks / Trade-offs

- [Simple queries may be over-decomposed] -> Mitigation: keep threshold at 2 research tasks (not higher), monitor latency and token deltas.
- [Legacy clients rely on old semantic differences] -> Mitigation: alias mapping plus deprecation logging and migration note.
- [Test regressions across strategy assumptions] -> Mitigation: update tests in one batch with explicit unified-semantics assertions.
- [Higher token spend due to mandatory merge] -> Mitigation: rollout gate with cost ceiling and rollback trigger.

## Migration Plan

1. Product surface migration
- Remove visible strategy options except unified entry.
- Keep request payload shape stable where possible.

2. Backend semantic convergence
- Normalize incoming strategy aliases to unified semantics.
- Emit deprecation signals for legacy aliases.

3. Decomposition/dependency enforcement
- Apply minimum multi-agent threshold and mandatory `task-merge` dependency rules.

4. Validation and release gate
- Re-run single/regression quality evaluation and collect cost/latency metrics.
- Promote only if thresholds pass; otherwise rollback to previous behavior via feature/config toggle.

## Open Questions

- Should alias compatibility be time-bounded (e.g., one release cycle) or indefinite?
- Should deprecated alias use be surfaced only in logs or also in API response metadata?
- What exact cost increase ceiling is acceptable for full rollout (e.g., +20%, +30%)?
