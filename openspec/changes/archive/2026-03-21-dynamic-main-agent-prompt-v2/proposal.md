## Why

Current orchestration prompts are optimized for decomposition and retrieval flow, but not for mandatory cross-agent integration before final synthesis. This leads to structurally correct yet low-decision-value outputs and weak traceability from final claims back to evidence.

## What Changes

- Introduce a v2 prompt architecture where the main agent performs a mandatory Evidence Integration Gate after collecting all child-agent outputs.
- Upgrade the main-agent prompt from static role routing to dynamic child-agent identity definition per query complexity and uncertainty.
- Define a domain-agnostic child-agent task contract template that enforces scope, source policy, evidence requirements, output schema, and acceptance criteria.
- Add explicit integration deliverables (canonical facts, claim-evidence map, conflicts, uncertainties, gap ledger) as required handoff into final synthesis.
- Standardize dependency semantics so synthesis depends on integration output rather than raw parallel outputs.

## Capabilities

### New Capabilities
- `dynamic-agent-prompt-orchestration`: Dynamic main/child prompt framework with a mandatory integration stage and explicit dependency contracts.

### Modified Capabilities
- `prompt-expert-service`: Expand prompt contract expectations to support dynamic role identity composition, integration-aware constraints, and claim-to-evidence traceability requirements.

## Impact

- Affected prompt assets in llm_service orchestration/decomposition/execution/final synthesis layers.
- Affected planning and handoff semantics in task contracts (without requiring immediate data-model migration).
- Potential updates to workflow templates and evaluation criteria to reflect integration-gated synthesis quality.
- No required external dependency changes for initial rollout; can run as prompt-only upgrade first.
