from shannon.utils.env import load_env

# 中文注释：优先加载 .env，避免客户端在导入时拿不到连接串而降级到内存
load_env()

from shannon.orchestration.orchestrator.app import app

# 中文注释：编排层 FastAPI 应用入口
# 中文注释：此处直接复用 orchestrator 子模块中的 FastAPI 实例
