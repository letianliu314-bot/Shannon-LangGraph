from __future__ import annotations

import re
from typing import Any, Dict, List, Set
from urllib.parse import urlparse

from shannon.llm_service.retrieval.crawler import web_crawl
from shannon.llm_service.retrieval.fetcher import web_fetch
from shannon.llm_service.retrieval.search import web_search
from shannon.llm_service.retrieval.selector import select_candidate_urls

QUERY_NOISE_TERMS = {
    "independently",
    "research",
    "synthesize",
    "improvements",
    "focusing",
    "focus",
    "architecture",
    "training",
    "efficiency",
    "cost",
    "context",
    "length",
    "tool",
    "agentic",
    "capability",
    "benchmark",
    "methodology",
    "generate",
    "exactly",
    "jsonl",
    "samples",
    "evidence",
    "fetched",
    "source",
    "sources",
}

PAPER_DOMAINS = {
    "arxiv.org",
    "openreview.net",
    "aclanthology.org",
    "paperswithcode.com",
    "semanticscholar.org",
    "huggingface.co",
    "github.com",
}


# 中文注释：Search-first 检索流程


def _build_query_variants(query: str) -> List[str]:
    # 中文注释：逐轮扩展查询，避免一轮抓取不足
    base = query.strip()
    if not base:
        return [""]
    return [
        base,
        f"{base} official documentation",
        f"{base} primary source",
    ]


def _query_term_match_ratio(query: str, fetched_pages: List[Dict[str, Any]]) -> float:
    terms = [
        t
        for t in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", (query or "").lower())
        if len(t) >= 4 and t not in QUERY_NOISE_TERMS
    ]
    if not terms:
        return 1.0
    hits = 0
    for page in fetched_pages:
        text = f"{page.get('title') or ''} {page.get('content') or ''}".lower()
        if any(term in text for term in terms[:8]):
            hits += 1
    return hits / max(1, len(fetched_pages))


def _is_paper_query(query: str) -> bool:
    lowered = (query or "").lower()
    markers = [
        "paper",
        "technical report",
        "arxiv",
        "openreview",
        "论文",
        "技术报告",
    ]
    return any(marker in lowered for marker in markers)


def _paper_source_coverage(query: str, fetched_pages: List[Dict[str, Any]]) -> bool:
    if not _is_paper_query(query):
        return True
    focus_terms = [t for t in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", (query or "").lower()) if len(t) >= 4 and t not in QUERY_NOISE_TERMS]
    for page in fetched_pages:
        domain = (urlparse(str(page.get("url") or "")).netloc or "").lower()
        if not domain:
            continue
        if any(domain == item or domain.endswith(f".{item}") for item in PAPER_DOMAINS):
            return True
        if any(term in domain for term in focus_terms):
            return True
    return False


def _quality_gate(query: str, fetched_pages: List[Dict[str, Any]]) -> bool:
    # 中文注释：质量门：数量、正文长度、与 query 的匹配度
    ok_pages = [p for p in fetched_pages if p.get("status") == "ok"]
    if len(ok_pages) < 2:
        return False

    total_chars = sum(len(str(p.get("content") or "")) for p in ok_pages)
    if total_chars < 1800:
        return False

    if not _paper_source_coverage(query, ok_pages):
        return False

    return _query_term_match_ratio(query, ok_pages) >= 0.3


def run_search_first_pipeline(
    query: str,
    max_rounds: int = 2,
    per_round_fetch_limit: int = 3,
    max_search_results: int = 8,
    domains: List[str] | None = None,
    source_guidance: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    # 中文注释：流程：Search(Tavily) -> URL Select -> Fetch/Crawl(受控) -> evidence 输出
    query_variants = _build_query_variants(query)

    seen_urls: Set[str] = set()
    all_candidates: List[Dict[str, Any]] = []
    selected_records: List[Dict[str, Any]] = []
    fetched_pages: List[Dict[str, Any]] = []
    rounds: List[Dict[str, Any]] = []
    domain_allowlist = [str(item).strip() for item in (domains or []) if str(item).strip()]
    source_guidance = source_guidance if isinstance(source_guidance, dict) else {}
    required_sources = (
        [str(item).strip().lower() for item in (source_guidance.get("required") or []) if str(item).strip()]
        if source_guidance
        else []
    )
    avoid_sources = (
        [str(item).strip().lower() for item in (source_guidance.get("avoid") or []) if str(item).strip()]
        if source_guidance
        else []
    )

    for round_index in range(max(1, min(max_rounds, 3))):
        active_query = query_variants[min(round_index, len(query_variants) - 1)]
        candidates = web_search(active_query, max_results=max_search_results, domains=domain_allowlist or None)
        all_candidates.extend(candidates)

        selected = select_candidate_urls(
            query=active_query,
            candidates=candidates,
            max_urls=per_round_fetch_limit,
            seen_urls=seen_urls,
            required_sources=required_sources,
            avoid_sources=avoid_sources,
        )

        selected_urls = [str(item.get("url") or "") for item in selected if str(item.get("url") or "")]
        for url in selected_urls:
            seen_urls.add(url)
        selected_records.extend(selected)

        fetched = web_fetch(selected_urls, max_chars=12000)
        fetched_pages.extend(fetched)

        rounds.append(
            {
                "round": round_index + 1,
                "query": active_query,
                "candidate_count": len(candidates),
                "selected_count": len(selected_urls),
                "fetched_count": len(fetched),
            }
        )

        if _quality_gate(active_query, fetched_pages):
            break

    # 中文注释：抓取质量不足时，触发受控 crawl 扩展（仅对已选 URL）
    if not _quality_gate(query, fetched_pages) and selected_records:
        crawl_seed_urls = [str(item.get("url")) for item in selected_records[:2] if item.get("url")]
        crawl_result = web_crawl(crawl_seed_urls, max_pages_per_seed=2, max_total_pages=4)
        crawl_pages = crawl_result.get("pages") if isinstance(crawl_result, dict) else []
        if isinstance(crawl_pages, list):
            fetched_pages.extend(crawl_pages)
        rounds.append(
            {
                "round": len(rounds) + 1,
                "query": "controlled_crawl",
                "candidate_count": len(crawl_seed_urls),
                "selected_count": len(crawl_seed_urls),
                "fetched_count": len(crawl_pages) if isinstance(crawl_pages, list) else 0,
            }
        )

    # 中文注释：按 content_hash 去重，保留最先抓到的版本
    unique_pages: List[Dict[str, Any]] = []
    seen_hashes: Set[str] = set()
    for page in fetched_pages:
        if not isinstance(page, dict):
            continue
        content_hash = str(page.get("content_hash") or "")
        if content_hash and content_hash in seen_hashes:
            continue
        if content_hash:
            seen_hashes.add(content_hash)
        unique_pages.append(page)

    return {
        "query": query,
        "rounds": rounds,
        "candidates": all_candidates,
        "selected_urls": selected_records,
        "fetched_pages": unique_pages,
            "metrics": {
                "candidate_total": len(all_candidates),
                "selected_total": len(selected_records),
                "fetched_total": len(unique_pages),
                "quality_passed": _quality_gate(query, unique_pages),
                "domain_allowlist": domain_allowlist,
                "required_sources": required_sources,
                "avoid_sources": avoid_sources,
            },
    }
