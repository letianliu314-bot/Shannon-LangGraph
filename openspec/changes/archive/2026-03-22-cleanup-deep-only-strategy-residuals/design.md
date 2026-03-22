## Context

The codebase has already converged runtime behavior to unified deep semantics, but residual legacy strategy constructs remain in prompts, runtime metadata, tests, and documentation. These residuals create semantic drift: developers can still encounter `quick/standard` guidance in prompt text, and API/event payloads still expose deprecated alias observability fields that are no longer needed after migration close.

This change is cross-cutting across llm-service prompt assembly, orchestration metadata, tests, docs, and OpenSpec lifecycle cleanup for the previous rollout change.

## Goals / Non-Goals

**Goals:**
- Remove legacy strategy prompt branches and align prompt semantics to deep-only behavior.
- Remove obsolete strategy-specific runtime branching where behavior is already unified.
- Remove deprecated alias observability fields from orchestrator metadata and events.
- Remove temporary validation scripts/artifacts used only for one-time rollout verification.
- Update user-facing docs/examples to deep-only wording and remove selectable quick/standard/deep language.
- Archive `unify-single-multi-agent-strategy` before deleting its active change directory.

**Non-Goals:**
- No change to core multi-agent topology enforcement (`task-merge` injection/dependency constraints).
- No redesign of planner execution model or retrieval stack.
- No new API capability introduction beyond cleanup/removal.

## Decisions

1. Prompt strategy cleanup is treated as behavioral consistency, not feature expansion.
- Decision: remove legacy `STRATEGY_GUIDANCE.quick/standard` branches and converge decomposition/research-supervisor prompt language to one canonical deep-oriented path.
- Rationale: avoids hidden fallback semantics and terminology overlap.
- Alternatives considered:
  - Keep legacy branches but never call them: rejected due to future drift risk.
  - Keep branches behind feature flag: rejected as unnecessary operational complexity.

2. Remove alias observability metadata post-migration.
- Decision: remove `strategy_requested` and `strategy_alias_deprecated` from state/session/manifest/event metadata.
- Rationale: migration period is closed; fields now increase payload surface without product value.
- Alternatives considered:
  - Keep fields indefinitely for analytics: rejected; analytics can use normalized strategy and historical logs.
  - Keep fields but mark deprecated in docs: rejected; leaves long-tail maintenance burden.

3. Remove temporary validation artifacts from tracked workspace scope.
- Decision: delete one-off script/report outputs generated for rollout checkpointing.
- Rationale: avoids stale benchmark data being mistaken for active baseline.
- Alternatives considered:
  - Keep in place for convenience: rejected due to clutter and interpretation risk.
  - Move to archival storage first: acceptable only if team needs long-term audit snapshots.

4. Archive-first policy for completed change cleanup.
- Decision: archive `unify-single-multi-agent-strategy` before removing active change directory.
- Rationale: preserve historical decision chain and spec deltas.
- Alternatives considered:
  - Direct deletion: rejected; loses traceability.

## Risks / Trade-offs

- [Breaking downstream consumers expecting alias observability fields] -> Mitigation: mark removal as BREAKING, update API/event docs, announce migration notice.
- [Accidental removal of still-needed historical evidence] -> Mitigation: archive change and optionally retain an immutable snapshot outside active reports path.
- [Prompt wording cleanup changes decomposition distribution unexpectedly] -> Mitigation: run targeted decomposition regression tests after cleanup.
- [Doc lag leaves conflicting instructions] -> Mitigation: include README/docs updates in same cleanup wave and verify grep for legacy user-choice wording.

## Migration Plan

1. Archive completed change `unify-single-multi-agent-strategy`.
2. Remove prompt/runtime/test legacy strategy residues in one coherent cleanup PR.
3. Remove temporary script and stress reports from active tracked paths.
4. Update README/docs examples to deep-only semantics.
5. Execute focused validation:
- unit tests for llm-service/orchestrator prompt behavior
- checks for event payload compatibility expectations
- grep-based validation for user-facing legacy strategy wording
6. Rollback strategy:
- Revert cleanup commit to restore removed fields/text if critical downstream dependency is discovered.

## Open Questions

- Should deprecated alias observability be preserved in external telemetry pipelines before code-level removal?
- Do we want to keep a permanent historical benchmark copy under a dedicated archive reports namespace?
- Should complexity labels in prompt text avoid the word `standard` entirely to prevent semantic overlap with deprecated strategy naming?
