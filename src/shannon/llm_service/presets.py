from __future__ import annotations

from typing import Dict, List, TypedDict

# 中文注释：角色预设定义（system prompt + 工具白名单）


class AgentPreset(TypedDict):
    # 中文注释：角色系统提示词
    system_prompt: str
    # 中文注释：允许使用的工具白名单
    tools_allowed: List[str]


PRESETS: Dict[str, AgentPreset] = {
    "deep_research_agent": {
        "system_prompt": (
            "You are a rigorous research agent. "
            "Always follow Search-first workflow: web_search -> url_select -> web_fetch/web_crawl -> synthesize. "
            "Cite only fetched evidence."
        ),
        "tools_allowed": ["web_search", "url_select", "web_fetch", "web_crawl", "mcp_fetch"],
    },
    "research_synthesizer": {
        "system_prompt": "You are a synthesis agent. Merge multi-task outputs into a coherent final answer with clear structure.",
        "tools_allowed": [],
    },
}


# 中文注释：函数 get_preset 的入口

def get_preset(name: str) -> AgentPreset:
    # 中文注释：未命中时回退到 deep_research_agent
    return PRESETS.get(name, PRESETS["deep_research_agent"])
