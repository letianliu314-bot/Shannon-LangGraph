import time

# 中文注释：指标采集（简化版）


class Metrics:
    # 中文注释：函数 __init__ 的入口
    def __init__(self) -> None:
        # 中文注释：记录起始时间与计数器
        self.start_time = time.time()
        self.success_count = 0
        self.fail_count = 0

    # 中文注释：函数 record_success 的入口
    def record_success(self) -> None:
        # 中文注释：成功次数加一
        self.success_count += 1

    # 中文注释：函数 record_fail 的入口
    def record_fail(self) -> None:
        # 中文注释：失败次数加一
        self.fail_count += 1

    # 中文注释：函数 elapsed 的入口
    def elapsed(self) -> float:
        # 中文注释：返回耗时
        return time.time() - self.start_time
