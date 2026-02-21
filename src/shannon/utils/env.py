import os

from dotenv import load_dotenv

# 中文注释：环境变量加载与校验


def load_env() -> None:
    # 中文注释：加载 .env 文件
    load_dotenv()


# 中文注释：函数 get_env 的入口
def get_env(key: str, default: str | None = None) -> str | None:
    # 中文注释：读取环境变量，支持默认值
    return os.getenv(key, default)
