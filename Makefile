# 中文注释：项目常用命令

PYTHON ?= python
PYTHONPATH ?= src

init:
	@echo "初始化环境变量示例"
	@cp -n .env.example .env || true

install:
	@echo "安装依赖"
	@${PYTHON} -m pip install -r requirements.txt

run-orchestration:
	@echo "启动编排层"
	@PYTHONPATH=${PYTHONPATH} ${PYTHON} -m uvicorn shannon.orchestration.main:app --reload --port 8000 --reload-exclude 'tests/*' --reload-exclude 'desktop/*' --reload-exclude 'migrations/*'

run-llm:
	@echo "启动 LLM Service"
	@PYTHONPATH=${PYTHONPATH} ${PYTHON} -m uvicorn shannon.llm_service.main:app --reload --port 8001 --reload-exclude 'tests/*' --reload-exclude 'desktop/*' --reload-exclude 'migrations/*'

test:
	@echo "运行测试"
	@PYTHONPATH=${PYTHONPATH} ${PYTHON} -m pytest -q
