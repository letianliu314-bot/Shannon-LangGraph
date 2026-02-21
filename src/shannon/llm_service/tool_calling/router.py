from __future__ import annotations

from typing import Any, Dict, List

from shannon.llm_service.client.mcp_client import MCPClient
from shannon.llm_service.retrieval.crawler import web_crawl
from shannon.llm_service.retrieval.fetcher import web_fetch
from shannon.llm_service.retrieval.search import web_search
from shannon.llm_service.retrieval.selector import select_candidate_urls

# 中文注释：工具路由


def route_tool_call(tool_call: dict):
    # 中文注释：解析工具名称与参数
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("arguments", {})
    if not isinstance(tool_args, dict):
        raise ValueError("工具参数必须是对象")

    # 中文注释：检索层 1：web_search（Tavily）
    if tool_name in {"web_search", "tavily_search"}:
        query = str(tool_args.get("query") or "")
        max_results = int(tool_args.get("max_results", 8) or 8)
        domains = tool_args.get("domains")
        normalized_domains: List[str] = domains if isinstance(domains, list) else []
        return {
            "results": web_search(
                query=query,
                max_results=max_results,
                domains=normalized_domains,
            )
        }

    # 中文注释：URL 选择器：从候选结果挑选高价值 URL
    if tool_name == "url_select":
        query = str(tool_args.get("query") or "")
        candidates = tool_args.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("url_select 需要 candidates 列表参数")
        max_urls = int(tool_args.get("max_urls", 3) or 3)
        return {"selected": select_candidate_urls(query=query, candidates=candidates, max_urls=max_urls)}

    # 中文注释：检索层 2：web_fetch（受控抓取）
    if tool_name == "web_fetch":
        urls_raw = tool_args.get("urls")
        if isinstance(urls_raw, list):
            urls = [str(u) for u in urls_raw if str(u).strip()]
        else:
            single_url = str(tool_args.get("url") or "").strip()
            urls = [single_url] if single_url else []
        max_chars = int(tool_args.get("max_chars", 12000) or 12000)
        return {"pages": web_fetch(urls=urls, max_chars=max_chars)}

    # 中文注释：检索层 2：web_crawl（受控小规模扩展）
    if tool_name == "web_crawl":
        seeds_raw = tool_args.get("seed_urls")
        if isinstance(seeds_raw, list):
            seed_urls = [str(u) for u in seeds_raw if str(u).strip()]
        else:
            single_url = str(tool_args.get("url") or "").strip()
            seed_urls = [single_url] if single_url else []
        return web_crawl(
            seed_urls=seed_urls,
            max_pages_per_seed=int(tool_args.get("max_pages_per_seed", 2) or 2),
            max_total_pages=int(tool_args.get("max_total_pages", 6) or 6),
            max_chars=int(tool_args.get("max_chars", 10000) or 10000),
        )

    # 中文注释：以 mcp_ 前缀路由到 MCP 工具
    if tool_name and tool_name.startswith("mcp_"):
        return MCPClient().call(tool_name, tool_args)
    # 中文注释：未知工具则抛出异常
    raise ValueError(f"未知工具：{tool_name}")
