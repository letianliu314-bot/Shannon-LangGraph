from __future__ import annotations

from typing import List, Optional

from shannon.llm_service.prompts.research_supervisor import (
    DOMAIN_ANALYSIS_HINT,
    RESEARCH_SUPERVISOR_IDENTITY,
)

# 中文注释：分解提示词版本
PROMPT_VERSION = "v2.0"

# 中文注释：通用规划身份（来自原项目）
GENERAL_PLANNING_IDENTITY = (
    "You are a planning assistant. Analyze the user's task and determine if it needs decomposition.\n"
    "IMPORTANT: Process queries in ANY language including English, Chinese, Japanese, Korean, etc.\n\n"
    "For SIMPLE queries (single action, direct answer, or basic calculation), set complexity_score < 0.3 and provide a single subtask.\n"
    "For COMPLEX queries (multiple steps, dependencies), set complexity_score >= 0.3 and decompose into multiple subtasks.\n\n"
)

# 中文注释：通用分解后缀（高度复用原项目结构，仅对可用工具做最小替换）
COMMON_DECOMPOSITION_SUFFIX_TEMPLATE = (
    "CRITICAL: Each subtask MUST have these EXACT fields: id, description, dependencies, estimated_tokens, suggested_tools, tool_parameters\n"
    "NEVER return null for subtasks field - always provide at least one subtask.\n\n"
    "TOOL SELECTION GUIDELINES:\n"
    "Default: Use NO TOOLS unless the task requires external data retrieval or computation.\n\n"
    "## WEB RESEARCH STRATEGY: Search First, Then Fetch\n\n"
    "### DEFAULT PATTERN (prefer SINGLE subtask):\n"
    "- Keep retrieval in ONE subtask whenever possible.\n"
    "- Inside that subtask, follow search-first flow: web_search -> url_select -> web_fetch/web_crawl.\n"
    "- For specific domain, use query='site:example.com [topic]'.\n"
    "- Only split retrieval into multiple subtasks when a downstream task truly requires upstream output.\n\n"
    "### WHEN TO ADD DEPENDENCIES:\n"
    "- Add dependency ONLY for hard data handoff (e.g., transform/summarize/JSONL generation must consume fetched evidence).\n"
    "- Do NOT add dependency just to separate search/select/fetch into different subtasks.\n\n"
    "### CONTROLLED CRAWL (fallback only):\n"
    "- web_crawl: ONLY when fetch evidence is insufficient and site structure is unclear\n"
    "- Keep crawl controlled: small page limit, high-value paths first\n\n"
    "## COMPANY/ENTITY RESEARCH WORKFLOW:\n"
    "1. Search first: '[company] [topic]' or 'site:[company].com [topic]'\n"
    "2. Include intent keywords in search: pricing, cost, plan, tier, 价格, 定价, 套餐 (if relevant)\n"
    "3. Select + Fetch: Top relevant URLs from search results\n"
    "4. Business directories: 'site:crunchbase.com [company]', 'site:linkedin.com [company]'\n"
    "5. Asian companies: Include Japanese/Chinese name variants in searches\n\n"
    "## Deep Research 2.0: Task Contracts (Optional, but REQUIRED for research workflows)\n"
    "For research workflows, you MAY include these fields to define explicit task boundaries:\n"
    "- output_format: {type: 'structured'|'narrative', required_fields: [...], optional_fields: [...]}\n"
    "- source_guidance: {required: ['official', 'aggregator'], optional: ['news'], avoid: ['social']}\n"
    "- search_budget: {max_queries: 5, max_fetches: 10}\n"
    "- boundaries: {in_scope: ['topic1', 'topic2'], out_of_scope: ['topic3']}\n\n"
    "Source type values: 'official' (company/.gov/.edu), 'aggregator' (crunchbase/wikipedia), "
    "'news' (recent articles), 'academic' (arxiv/papers), 'github', 'financial', 'local_cn', 'local_jp'\n\n"
    "Return ONLY valid JSON with this EXACT structure (no additional text):\n"
    "{\n"
    '  "mode": "standard",\n'
    '  "complexity_score": 0.5,\n'
    '  "subtasks": [\n'
    "    {\n"
    '      "id": "task-1",\n'
    '      "description": "Task description",\n'
    '      "dependencies": [],\n'
    '      "estimated_tokens": 500,\n'
    '      "suggested_tools": [],\n'
    '      "tool_parameters": {},\n'
    '      "output_format": {"type": "narrative", "required_fields": [], "optional_fields": []},\n'
    '      "source_guidance": {"required": ["official"], "optional": ["news"]},\n'
    '      "search_budget": {"max_queries": 10, "max_fetches": 20},\n'
    '      "boundaries": {"in_scope": ["topic"], "out_of_scope": []}\n'
    "    }\n"
    "  ],\n"
    '  "execution_strategy": "parallel_preferred",\n'
    '  "concurrency_limit": 3,\n'
    '  "token_estimates": {"task-1": 500},\n'
    '  "total_estimated_tokens": 500\n'
    "}\n\n"
    "CRITICAL: Tool parameters MUST use EXACT parameter names from schemas. See available tools below.\n\n"
    "{tool_schemas_text}\n\n"
    "Rules:\n"
    '- mode: must be "simple", "standard", or "complex"\n'
    "- complexity_score: number between 0.0 and 1.0\n"
    "- dependencies: array of task ID strings or empty array []\n"
    "- suggested_tools: empty array [] if no tools needed, otherwise list tool names\n"
    "- tool_parameters: empty object {} if no tools, otherwise parameters for the tool\n"
    "- source_guidance: (optional) object with required/optional/avoid source type arrays\n"
    "- boundaries: (optional) object with in_scope/out_of_scope topic arrays\n"
    "- For subtasks with non-empty dependencies, DO NOT prefill tool_parameters; set it to {} and avoid placeholders (the agent will use previous_results to construct exact parameters).\n"
    "- Do NOT split one retrieval flow into chained subtasks unless strictly required by data handoff.\n"
    "- For transform tasks (sort/select/extract/generate JSONL), prefer using dependencies over fresh web_search.\n"
    "- Let the semantic meaning of the query guide tool selection\n"
)

# 中文注释：研究策略引导（来自原项目）
STRATEGY_GUIDANCE = {
    "quick": (
        "\n\nRESEARCH STRATEGY: quick\n"
        "- Override the generic simple/complex ranges for this query.\n"
        "- Prefer 1-3 broad subtasks that cover the main question.\n"
        "- Focus on a high-level overview instead of exhaustive coverage.\n"
        "- Avoid splitting into many narrow subtasks.\n"
        "- Aim for complexity_score < 0.4.\n"
    ),
    "standard": (
        "\n\nRESEARCH STRATEGY: standard\n"
        "- Override the generic simple/complex ranges for this query.\n"
        "- Prefer 3-5 focused subtasks that cover the key dimensions of the query.\n"
        "- Balance breadth and depth; avoid unnecessary fragmentation.\n"
        "- Aim for complexity_score between 0.4 and 0.6.\n"
    ),
    "deep": (
        "\n\nRESEARCH STRATEGY: deep\n"
        "- Override the generic simple/complex ranges for this query.\n"
        "- Prefer 5-8 specialized subtasks that each explore a distinct aspect.\n"
        "- Include follow-up subtasks when clarification or cross-checking is needed.\n"
        "- Aim for complexity_score between 0.6 and 0.8.\n"
    ),
}


# 中文注释：函数 _build_tool_schemas_text 的入口

def _build_tool_schemas_text(available_tools: Optional[List[str]]) -> str:
    tools = available_tools or ["web_search", "url_select", "web_fetch", "web_crawl"]
    return (
        "AVAILABLE TOOLS:\n"
        + "\n".join([f"- {tool}" for tool in tools])
    )


# 中文注释：函数 build_decompose_system_prompt 的入口

def build_decompose_system_prompt(
    strategy: str,
    query_type: Optional[str],
    research_areas: Optional[List[str]],
    available_tools: Optional[List[str]] = None,
    current_date: Optional[str] = None,
    decomposition_prompt: Optional[str] = None,
    is_research_context: bool = True,
) -> str:
    # 中文注释：按原项目架构拼接 decompose system prompt
    if decomposition_prompt:
        identity_prompt = decomposition_prompt
        prompt_source = "explicit_override"
    elif is_research_context:
        identity_prompt = RESEARCH_SUPERVISOR_IDENTITY
        prompt_source = "research"
    else:
        identity_prompt = GENERAL_PLANNING_IDENTITY
        prompt_source = "general"

    tool_schemas_text = _build_tool_schemas_text(available_tools)
    # 中文注释：避免 JSON 示例中的大括号被 str.format 误解析，使用 replace 注入工具说明
    common_suffix = COMMON_DECOMPOSITION_SUFFIX_TEMPLATE.replace("{tool_schemas_text}", tool_schemas_text)

    date_prefix = f"The current date is {current_date}.\n\n" if current_date else ""
    prompt = date_prefix + identity_prompt + common_suffix

    if isinstance(query_type, str) and query_type.strip().lower() == "company":
        prompt += DOMAIN_ANALYSIS_HINT

    strategy_key = (strategy or "").strip().lower()
    if prompt_source == "research" and strategy_key in STRATEGY_GUIDANCE:
        prompt += STRATEGY_GUIDANCE[strategy_key]

    if research_areas:
        valid_areas = [str(area) for area in research_areas if str(area).strip()]
        if valid_areas:
            areas_hint = (
                "\n\nRESEARCH AREA DECOMPOSITION:\n"
                f"- The user identified {len(valid_areas)} research areas.\n"
                "- Create 1-3 subtasks per area (break complex areas into focused steps).\n"
                f"- Set 'parent_area' for grouping; valid values: {valid_areas}.\n"
                "- Keep descriptions concise and ACTION-FIRST; start with a verb, not the area name.\n"
                "- Include 'parent_area' in each subtask JSON when research_areas are provided.\n"
            )
            prompt += areas_hint

    return prompt
