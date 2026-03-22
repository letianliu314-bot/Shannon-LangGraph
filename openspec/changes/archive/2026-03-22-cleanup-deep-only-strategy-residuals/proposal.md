## Why

The runtime strategy has already converged to deep-only semantics, but prompt templates, alias observability fields, tests, and docs still carry legacy quick/standard language. This drift creates ambiguity for maintainers and API consumers, and can reintroduce unintended branching behavior.

## What Changes

- Remove legacy strategy guidance branches from decomposition prompts (`quick`/`standard`) and keep one canonical deep-oriented planning instruction path.
- Remove legacy strategy-dependent runtime branches in llm-service where behavior is already unified.
- Remove orchestrator alias observability payload fields (`strategy_requested`, `strategy_alias_deprecated`) after migration close.
- **BREAKING**: stop emitting deprecated-alias observability fields in workflow start payload/session metadata/manifest metadata.
- Remove alias-compatibility test cases tied to deprecated observability behavior.
- Remove temporary validation scripts and stress report artifacts created for one-time rollout verification.
- Update public docs and examples to deep-only strategy wording; eliminate quick/standard/deep user-choice descriptions.
- Archive completed change `unify-single-multi-agent-strategy`, then clean its active change directory.

## Capabilities

### New Capabilities
- `deep-only-strategy-cleanup`: Define cleanup and consistency rules for removing legacy strategy residue across prompts, runtime metadata, tests, and docs.

### Modified Capabilities
- `dynamic-agent-prompt-orchestration`: Remove legacy strategy-tier prompt semantics and align decomposition/supervisor prompts to a single deep-only strategy contract.

## Impact

- Affected code:
  - `src/shannon/llm_service/prompts/decomposition.py`
  - `src/shannon/llm_service/prompts/research_supervisor.py`
  - `src/shannon/llm_service/main.py`
  - `src/shannon/orchestration/orchestrator/app.py`
  - `tests/unit/test_orchestrator_app_strategy.py`
- Affected docs/artifacts:
  - `README.md`
  - `docs/troubleshooting.md` and any deep-only-inconsistent docs
  - `deploy/scripts/_tmp_unify_strategy_cost_latency.py`
  - `reports/content_quality/stress/unify_strategy_*`
- API/event compatibility:
  - Consumers relying on alias observability metadata must migrate.
- Process impact:
  - Requires archive completion of `unify-single-multi-agent-strategy` before directory cleanup.
