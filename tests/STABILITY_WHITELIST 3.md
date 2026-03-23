# Stability Validation Whitelist

This change keeps the original stability validation scripts as baseline guardrails.

## Retained scripts
- deploy/scripts/phase1_memory_layer_acceptance.py
- deploy/scripts/phase2_orchestration_acceptance.py
- deploy/scripts/phase3_version_layer_acceptance.py
- deploy/scripts/phase4_prompt_expert_acceptance.py
- deploy/scripts/phase5_e2e_acceptance.py

## Notes
- Scripts above are treated as stability baselines and are not removed.
- Content-focused suite tests are separated under paradigm content acceptance assets.
