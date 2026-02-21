import logging

# 中文注释：日志配置


def setup_logging() -> None:
    # 中文注释：统一日志格式与级别
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
