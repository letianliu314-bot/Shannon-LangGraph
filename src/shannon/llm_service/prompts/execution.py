from __future__ import annotations

from typing import Optional

# 中文注释：研究执行阶段强约束提示词（复用原项目 RESEARCH MODE）
RESEARCH_MODE_INSTRUCTION = (
    "\n\nRESEARCH MODE - MANDATORY FETCH POLICY:"
    "\n- Search snippets are LEADS, NOT verified content. You MUST fetch to verify."
    "\n- After EACH web_search, you MUST call web_fetch on ALL potentially relevant URLs."
    "\n- Only skip URLs that are CLEARLY irrelevant (e.g., wrong language, completely different topic, broken links)."
    "\n- Use batch fetch: web_fetch(urls=[url1, url2, ...]) for efficiency."
    "\n- Minimum: fetch at least 5-8 URLs per search, or ALL results if fewer."
    "\n\nTOOL USAGE (CRITICAL):"
    "\n- Invoke tools ONLY via native function calling (no XML/JSON stubs like <web_fetch> or <function_calls>)."
    "\n- ALWAYS use batch fetch: web_fetch(urls=[...]) instead of single URL calls."
    "\n\nSOURCE EVALUATION AND CONFLICT RESOLUTION:"
    "\n1. VERIFICATION (MANDATORY): Search snippets are NOT facts. You MUST web_fetch EVERY source before citing it."
    "\n2. SPECULATIVE LANGUAGE: Mark uncertain claims (reportedly, allegedly, may, sources suggest)."
    "\n3. SOURCE PRIORITY (highest to lowest):"
    "\n   - Official sources (company website, .gov, .edu, investor relations)"
    "\n   - Authoritative aggregators (Crunchbase, LinkedIn, Wikipedia)"
    "\n   - News outlets (Reuters, Bloomberg, TechCrunch)"
    "\n   - Blog posts, forums, social media"
    "\n4. TIME PRIORITY:"
    "\n   - For DYNAMIC topics (pricing, team, products, market data): prefer sources from last 6-12 months"
    "\n   - For STATIC topics (founding date, history): any authoritative source"
    "\n5. CONFLICT HANDLING (MANDATORY when sources disagree):"
    "\n   - LIST all conflicting claims with their sources and dates"
    "\n   - RANK by: (1) source authority, (2) recency"
    "\n   - EXPLICITLY STATE which version you prioritize and WHY"
)

# 中文注释：证据综合提示词（源格式）
INTERPRETATION_PROMPT_SOURCES = """=== CRITICAL INSTRUCTION ===

You MUST summarize the ACTUAL CONTENT from the tool results above.
You MUST assess each source's RELEVANCE to the original query.

=== EVIDENCE-ONLY CONSTRAINT (CRITICAL) ===

STRICT RULES - violation causes output rejection:
1. Every URL you mention MUST appear in the tool results above
2. If a tool returned an error or empty content, report it as-is
3. DO NOT infer, guess, or fabricate any data not present in tool results
4. If tool says "Site Error", "Access Denied", "404", "no content" -> report the failure, nothing more

=== OUTPUT FORMAT ===

# PART 1 - RETRIEVED INFORMATION

## Source 1: [URL]
[high/low relevance summary]

## Source 2: [URL]
...

# PART 2 - NOTES (optional)
[Conflicts between sources, data gaps, failed fetches summary]

ONLY summarize what was ALREADY retrieved."""

# 中文注释：证据综合提示词（通用问答格式）
INTERPRETATION_PROMPT_GENERAL = """=== CRITICAL INSTRUCTION ===

You MUST answer the original query using ONLY the tool results above.

RULES:
- Provide a clear, complete answer (not raw tool logs).
- Do NOT mention tool names or the tool-calling process.
- If the tool results are insufficient, say so explicitly.
- Do NOT invent facts, sources, or URLs.

ONLY use information that was ALREADY retrieved."""

# 中文注释：研究角色集合（复用原项目）
SOURCE_FORMAT_ROLES = {"deep_research_agent", "research", "domain_prefetch"}


# 中文注释：函数 should_use_source_format 的入口

def should_use_source_format(role: Optional[str]) -> bool:
    if not role:
        return False
    return role.strip().lower() in SOURCE_FORMAT_ROLES
