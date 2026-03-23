#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python deploy/scripts/phase1_memory_layer_acceptance.py
python deploy/scripts/phase2_orchestration_acceptance.py
python deploy/scripts/phase3_version_layer_acceptance.py
python deploy/scripts/phase4_prompt_expert_acceptance.py
python deploy/scripts/phase5_e2e_acceptance.py
