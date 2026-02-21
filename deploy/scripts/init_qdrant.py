# 中文注释：初始化 Qdrant 索引

from pathlib import Path
import yaml


if __name__ == "__main__":
    config_path = Path(__file__).parents[2] / "config" / "vector_db" / "qdrant_init.yaml
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    print(f"Init Qdrant with: {config}")
