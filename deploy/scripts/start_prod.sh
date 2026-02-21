#!/usr/bin/env bash
# 中文注释：生产环境启动脚本
set -euo pipefail

uvicorn shannon.orchestration.main:app --host 0.0.0.0 --port 8000 &
uvicorn shannon.llm_service.main:app --host 0.0.0.0 --port 8001
