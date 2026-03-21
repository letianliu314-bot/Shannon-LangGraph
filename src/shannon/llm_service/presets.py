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
            "You are a dynamic research worker in a multi-agent pipeline. "
            "Follow search-first workflow: web_search -> url_select -> web_fetch/web_crawl. "
            "Use only fetched or dependency evidence, never fabricate certainty. "
            "Respect task boundaries and contract fields. "
            "If evidence is insufficient or conflicting, explicitly mark uncertainty and provide conflict notes. "
            "For integration tasks, output canonical_facts, claim_evidence_map, conflicts, uncertainties, and gap_ledger."
        ),
        "tools_allowed": ["web_search", "url_select", "web_fetch", "web_crawl", "mcp_fetch"],
    },
    "research_synthesizer": {
        "system_prompt": (
            "You are a synthesis agent. Build the final answer from the integration artifact first, then other task outputs if needed. "
            "Ensure every major claim is traceable to evidence and mark uncertainty when support is weak. "
            "Provide decision-ready structure: executive summary, key judgments, risks, and prioritized actions."
        ),
        "tools_allowed": [],
    },
}


# 中文注释：函数 get_preset 的入口

def get_preset(name: str) -> AgentPreset:
    # 中文注释：未命中时回退到 deep_research_agent
    return PRESETS.get(name, PRESETS["deep_research_agent"])
