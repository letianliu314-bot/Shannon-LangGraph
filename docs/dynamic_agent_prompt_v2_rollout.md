# Dynamic Agent Prompt v2 Rollout Guide

## 1. Field Mapping (v2 concepts -> current TaskContract fields)

- `complexity_level` -> `refined.complexity`
- `dynamic_role_identity` -> `description` plus Prompt Expert `role_prompt`
- `objective` -> `goal`
- `boundaries.in_scope/out_of_scope` -> `boundaries`
- `source_guidance` -> `source_guidance`
- `evidence_requirements` -> `acceptance_criteria` + `output_format.required_fields`
- `output_schema` -> `output_format`
- `dependency_semantics` -> `deps`
- `integration_brief` -> `task-merge` deliverable + structured output fields
- `traceability_requirements` -> Prompt Expert constraints + `claim_evidence_map` required field

## 2. Prompt-Only Phase Plan

1. Update main-agent planning prompt to v2 full structure.
2. Update runtime compact prompts for deep research and synthesizer.
3. Keep API/data model unchanged; encode new semantics in existing fields.
4. Ensure `task-merge` exists for multi-task research and synthesis consumes its output first.
5. Add contract validation checklist in execution prompt payload.

## 3. Typed-Field Migration Plan (Later)

1. Add first-class fields for `evidence_requirements`, `integration_brief`, and `quality_flags`.
2. Persist integration artifact as structured state rather than free-form content.
3. Add schema-level validation for claim-evidence traceability.

## 4. Acceptance Checkpoints

- Correctness stability: no regression in correctness metrics vs baseline.
- Integration traceability: `task-merge` outputs `claim_evidence_map`, `conflicts`, and `uncertainties`.
- Decision usefulness: final synthesis includes prioritized actions and explicit uncertainty notes.
- Dependency compliance: downstream synthesis/transform tasks depend on `task-merge` when present.
- Quality fallback: insufficient evidence paths label uncertainty instead of fabricating certainty.
