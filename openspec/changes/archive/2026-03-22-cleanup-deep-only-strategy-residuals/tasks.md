## 1. Prompt Strategy Residual Cleanup

- [x] 1.1 Remove `STRATEGY_GUIDANCE.quick` and `STRATEGY_GUIDANCE.standard` branches from `src/shannon/llm_service/prompts/decomposition.py`.
- [x] 1.2 Update decomposition/supervisor prompt wording to deep-only guidance and remove legacy strategy-tier phrasing.
- [x] 1.3 Ensure prompt output examples/rules do not imply selectable quick/standard strategy modes.

## 2. Runtime and Metadata Simplification

- [x] 2.1 Remove strategy-specific tier/complexity branch remnants in `src/shannon/llm_service/main.py` and keep unified deep semantics.
- [x] 2.2 Remove `strategy_requested` and `strategy_alias_deprecated` from orchestrator state/session/manifest/event payloads in `src/shannon/orchestration/orchestrator/app.py`.
- [x] 2.3 Verify no downstream code path still depends on removed alias observability fields.

## 3. Tests and Temporary Artifact Cleanup

- [x] 3.1 Remove deprecated alias compatibility test file `tests/unit/test_orchestrator_app_strategy.py`.
- [x] 3.2 Delete temporary script `deploy/scripts/_tmp_unify_strategy_cost_latency.py`.
- [x] 3.3 Delete temporary stress outputs `reports/content_quality/stress/unify_strategy_*` after confirming no long-term retention requirement.

## 4. Documentation and OpenSpec Lifecycle Alignment

- [x] 4.1 Update `README.md` and relevant docs to deep-only wording (remove quick/standard/deep user-choice language and outdated examples).
- [x] 4.2 Preserve `docs/dynamic_agent_prompt_v2_rollout.md` and keep references consistent with cleanup scope.
- [x] 4.3 Archive `unify-single-multi-agent-strategy` and then remove its active change directory per archive-first policy.

## 5. Validation and Regression Safeguards

- [x] 5.1 Run targeted unit tests for llm-service/orchestrator paths affected by strategy cleanup.
- [x] 5.2 Run grep-based checks to confirm legacy quick/standard strategy wording is removed from active docs/prompts.
- [x] 5.3 Confirm OpenSpec change `cleanup-deep-only-strategy-residuals` is apply-ready and summarize BREAKING metadata removal impact.
