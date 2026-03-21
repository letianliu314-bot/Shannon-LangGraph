## Context

Current decomposition prompts emphasize search-first retrieval and parallel task breakdown, but they do not enforce a mandatory post-collection integration stage before final synthesis. Prompt Expert currently returns a contract shell with role/task context, yet dynamic role identity composition and evidence-integration constraints are not first-class requirements. As a result, final outputs may be structurally clean but weak in cross-agent conflict handling, claim-to-evidence traceability, and decision usefulness.

## Goals / Non-Goals

**Goals:**
- Introduce a v2 main-agent prompt structure with an explicit Evidence Integration Gate between child-task execution and final synthesis.
- Define a domain-agnostic child-agent prompt/contract template that supports dynamic role identity, scope boundaries, source policies, evidence requirements, and output constraints.
- Preserve compatibility with current TaskContract fields so rollout can start as a prompt-only upgrade.
- Standardize dependency semantics: synthesis should depend on integration output, not raw parallel payloads.

**Non-Goals:**
- No immediate database schema change or new API endpoint requirement.
- No mandatory replacement of retrieval tooling.
- No full redesign of orchestration graph nodes in phase 1.

## Decisions

### Decision 1: Prompt-first upgrade with schema compatibility
- Choice: encode v2 semantics using existing fields (`goal`, `description`, `boundaries`, `source_guidance`, `output_format`, `acceptance_criteria`, `deps`, `role_preset`).
- Why: minimizes migration risk and allows controlled A/B verification.
- Alternative considered: add new typed fields (`integration_brief`, `evidence_requirements`) immediately. Rejected for phase 1 due to compatibility overhead.

### Decision 2: Mandatory integration task as an explicit dependency gate
- Choice: require one integration task (e.g., `task-merge`) that consumes all child research tasks and produces a structured integration brief.
- Why: forces canonicalization, deduplication, conflict adjudication, and uncertainty ledgering before final synthesis.
- Alternative considered: keep integration implicit in finalize prompt only. Rejected because it is hard to validate and easy to regress.

### Decision 3: Capability-based child identities
- Choice: dynamic child identity definitions (evidence scout, contradiction auditor, causal analyzer, scenario builder, decision translator) driven by query complexity.
- Why: avoids overfitting to AI-only domain roles and improves cross-domain portability.
- Alternative considered: fixed role library only. Rejected because it constrains decomposition quality for non-AI tasks.

### Decision 4: Claim-to-evidence traceability as a synthesis precondition
- Choice: integration output MUST include `claim_evidence_map`, `conflicts`, `uncertainties`, and `gap_ledger` before final synthesis is allowed.
- Why: prevents unsupported certainty and enables deterministic quality checks.
- Alternative considered: optional traceability notes. Rejected due to weak enforcement.

## Risks / Trade-offs

- [Risk] Prompt length growth increases latency and token cost. → Mitigation: keep compact system prompt for runtime and full planning prompt for decomposition only.
- [Risk] Over-constrained templates may reduce model flexibility in edge cases. → Mitigation: allow bounded optional fields and explicit uncertainty pathways.
- [Risk] Existing evaluation metrics may under-reward integration quality. → Mitigation: add integration-oriented acceptance checks in prompt contracts first, then update quality metrics in a later phase.
- [Risk] Merge task becomes bottleneck. → Mitigation: keep parallel research tasks broad but bounded; reserve heavy reasoning for merge only.

## Migration Plan

1. Introduce prompt v2 text assets for main agent and child contracts.
2. Route decomposition outputs to generate an explicit integration task with dependencies on all research tasks.
3. Update finalize prompt to consume integration brief as primary source.
4. Run existing stress regression baseline to confirm no correctness regressions.
5. Add follow-up quality calibration focused on integration traceability and decision usefulness.

Rollback strategy:
- Feature-flag prompt v2; revert to current prompt set if latency or quality regresses beyond tolerance.

## Open Questions

- Should integration brief be persisted as a first-class structured object in state, or remain encoded in task content during phase 1?
- Should Prompt Expert generate role identity from free text each run, or from a constrained capability taxonomy?
- What minimum confidence threshold should gate promotion from uncertainty to final recommendation?
