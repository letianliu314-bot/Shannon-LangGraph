from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from shannon.llm_service.client.tavily_client import TavilyClient

# 中文注释：检索层 1 - Web Search（Tavily）


def _compact_query(query: str, max_terms: int = 16) -> str:
    # 中文注释：压缩过长自然语言 query，减少搜索跑偏
    parts = [t for t in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", (query or "")) if t]
    if len(parts) <= max_terms:
        return query
    return " ".join(parts[:max_terms])


def web_search(
    query: str,
    max_results: int = 8,
    domains: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    # 中文注释：调用 Tavily 并统一输出结构 [{url,title,snippet,score,...}]
    compact_query = _compact_query(query)
    client = TavilyClient()
    response = client.search(
        query=compact_query,
        max_results=max_results,
        search_depth="advanced",
        include_raw_content=False,
        include_answer=False,
        domains=domains,
    )

    results = response.get("results") if isinstance(response, dict) else []
    if not isinstance(results, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        normalized.append(
            {
                "url": url,
                "title": str(item.get("title") or ""),
                "snippet": str(item.get("snippet") or item.get("content") or ""),
                "score": float(item.get("score") or 0.0),
                "published_date": item.get("published_date"),
                "source": item.get("source") or "tavily",
            }
        )

    return normalized
