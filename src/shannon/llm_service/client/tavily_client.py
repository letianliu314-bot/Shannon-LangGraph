from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

# 中文注释：Tavily 搜索客户端（支持真实调用 + 无 Key 兜底）


class TavilyClient:
    # 中文注释：函数 __init__ 的入口
    def __init__(self, timeout: float = 25.0) -> None:
        self.api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self.timeout = timeout
        self.base_url = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com").rstrip("/")

    # 中文注释：函数 _build_payload 的入口
    def _build_payload(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_raw_content: bool,
        include_answer: bool,
        domains: Optional[List[str]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max(1, min(max_results, 20)),
            "search_depth": search_depth,
            "include_raw_content": include_raw_content,
            "include_answer": include_answer,
        }
        if domains:
            # 中文注释：仅传递非空域名过滤
            include_domains = [d.strip() for d in domains if isinstance(d, str) and d.strip()]
            if include_domains:
                payload["include_domains"] = include_domains
        return payload

    # 中文注释：函数 search 的入口
    def search(
        self,
        query: str,
        max_results: int = 8,
        search_depth: str = "advanced",
        include_raw_content: bool = False,
        include_answer: bool = False,
        domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # 中文注释：无 API Key 时返回稳定兜底结构，避免流程中断
        if not self.api_key:
            return {
                "results": [],
                "answer": "",
                "query": query,
                "provider": "tavily",
                "note": "no_api_key",
            }

        payload = self._build_payload(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_raw_content=include_raw_content,
            include_answer=include_answer,
            domains=domains,
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/search", json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return {
                "results": [],
                "answer": "",
                "query": query,
                "provider": "tavily",
                "note": f"error:{type(exc).__name__}",
            }

        raw_results = data.get("results") if isinstance(data, dict) else []
        normalized: List[Dict[str, Any]] = []
        if isinstance(raw_results, list):
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "url": str(item.get("url") or ""),
                        "title": str(item.get("title") or ""),
                        "snippet": str(item.get("content") or item.get("snippet") or ""),
                        "score": float(item.get("score") or 0.0),
                        "published_date": item.get("published_date"),
                        "source": item.get("source", "tavily"),
                    }
                )

        return {
            "results": normalized,
            "answer": data.get("answer") if isinstance(data, dict) else "",
            "query": query,
            "provider": "tavily",
        }
