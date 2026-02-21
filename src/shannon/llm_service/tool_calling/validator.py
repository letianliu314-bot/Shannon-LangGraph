# 中文注释：工具调用参数校验


def validate_tool_call(tool_call: dict) -> None:
    # 中文注释：校验必须字段是否存在
    if "name" not in tool_call:
        raise ValueError("缺少工具名称")
    if "arguments" not in tool_call:
        raise ValueError("缺少工具参数")
    if not isinstance(tool_call.get("name"), str) or not tool_call.get("name"):
        raise ValueError("工具名称必须是非空字符串")
    if not isinstance(tool_call.get("arguments"), dict):
        raise ValueError("工具参数必须是对象")
