from shannon.llm_service.tool_calling.router import route_tool_call
from shannon.llm_service.tool_calling.validator import validate_tool_call

# 中文注释：工具执行入口


def execute_tool_call(tool_call: dict):
    # 中文注释：先进行参数校验
    validate_tool_call(tool_call)
    # 中文注释：通过路由执行具体工具
    return route_tool_call(tool_call)
