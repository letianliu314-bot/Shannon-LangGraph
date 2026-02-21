from __future__ import annotations

import re
from typing import Any, Dict, List, Set
from urllib.parse import urljoin, urlparse

from shannon.llm_service.retrieval.fetcher import web_fetch
from shannon.llm_service.retrieval.selector import HIGH_VALUE_PATH_KEYWORDS

# 中文注释：检索层 2 - Web Crawl（受控小规模扩展，不做全站爬取）


def _extract_links(base_url: str, raw_html: str) -> List[str]:
    # 中文注释：从 HTML 中提取链接并转绝对 URL
    if not raw_html:
        return []

    links = re.findall(r"href=[\"'](.*?)[\"']", raw_html, flags=re.IGNORECASE)
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    results: List[str] = []
    seen: Set[str] = set()

    for link in links:
        absolute = urljoin(base_url, link.strip())
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() != base_domain:
            continue
        normalized = absolute.split("#", 1)[0].rstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)

    return results


def _prioritize_links(links: List[str], max_links: int) -> List[str]:
    # 中文注释：优先选择高信息密度路径
    scored: List[tuple[float, str]] = []
    for url in links:
        parsed = urlparse(url)
        path = (parsed.path or "/").lower()
        score = 0.0

        if any(keyword in path for keyword in HIGH_VALUE_PATH_KEYWORDS):
            score += 1.0
        if path in {"", "/"}:
            score += 0.2

        # 中文注释：路径层级越浅越可能是高价值导航页
        depth = path.count("/")
        score += max(0.0, 0.4 - depth * 0.05)

        scored.append((score, url))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[: max(1, max_links)]]


def web_crawl(
    seed_urls: List[str],
    max_pages_per_seed: int = 2,
    max_total_pages: int = 6,
    max_chars: int = 10000,
) -> Dict[str, Any]:
    # 中文注释：受控爬取：每个 seed 最多扩展少量高价值子页面
    if not seed_urls:
        return {"pages": [], "metadata": {"total_crawled": 0, "strategy": "controlled"}}

    pages: List[Dict[str, Any]] = []
    visited: Set[str] = set()

    for seed in seed_urls:
        if len(pages) >= max_total_pages:
            break
        if seed in visited:
            continue

        seed_results = web_fetch([seed], max_chars=max_chars, include_raw_html=True)
        if not seed_results:
            continue
        seed_page = seed_results[0]
        seed_url = str(seed_page.get("url") or seed)
        visited.add(seed_url)
        pages.append(seed_page)

        if seed_page.get("status") != "ok":
            continue

        raw_html = str(seed_page.get("raw_html") or "")
        links = _extract_links(seed_url, raw_html)
        sub_links = _prioritize_links(links, max_links=max_pages_per_seed)

        for sub_url in sub_links:
            if len(pages) >= max_total_pages:
                break
            if sub_url in visited:
                continue
            child_results = web_fetch([sub_url], max_chars=max_chars, include_raw_html=False)
            if not child_results:
                continue
            child_page = child_results[0]
            visited.add(str(child_page.get("url") or sub_url))
            pages.append(child_page)

    # 中文注释：对外移除 raw_html，避免返回体过大
    clean_pages: List[Dict[str, Any]] = []
    for page in pages:
        page_copy = dict(page)
        page_copy.pop("raw_html", None)
        clean_pages.append(page_copy)

    return {
        "pages": clean_pages,
        "metadata": {
            "strategy": "controlled",
            "total_crawled": len(clean_pages),
            "seed_count": len(seed_urls),
            "max_pages_per_seed": max_pages_per_seed,
            "max_total_pages": max_total_pages,
        },
    }
