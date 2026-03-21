## 1. Main-Agent Prompt v2 Definition

- [x] 1.1 Draft compact main-agent system prompt v2 with mandatory Evidence Integration Gate
- [x] 1.2 Draft full planning prompt v2 covering complexity classification, dynamic child-role generation, contract enforcement, and integration-before-synthesis
- [x] 1.3 Add explicit failure policy for insufficient/conflicting evidence (uncertainty labeling, no fabricated certainty)

## 2. Child-Agent Contract Template v2

- [x] 2.1 Define domain-agnostic child-agent contract template fields (objective, boundaries, source policy, evidence rules, output schema, acceptance criteria)
- [x] 2.2 Define capability-based identity patterns and must-do/must-not-do constraints for dynamic role generation
- [x] 2.3 Define high-impact claim traceability requirements (claim-evidence map, conflict notes, uncertainty notes)

## 3. Dependency and Handoff Semantics

- [x] 3.1 Define integration task contract (`task-merge`) with required structured output fields: canonical_facts, claim_evidence_map, conflicts, uncertainties, gap_ledger
- [x] 3.2 Define dependency rule that synthesis depends on integration artifact rather than raw parallel outputs
- [x] 3.3 Define prompt-level validation checklist for contract completeness before task execution

## 4. Prompt-Only Rollout Plan

- [x] 4.1 Produce field mapping guide from v2 concepts to existing TaskContract fields without schema changes
- [x] 4.2 Define phased rollout plan (prompt-only first, typed-field migration later)
- [x] 4.3 Define acceptance checkpoints for regression safety (correctness stability, improved integration traceability, improved decision usefulness)
