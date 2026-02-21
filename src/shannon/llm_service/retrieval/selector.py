from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import urlparse

# 中文注释：URL 选择器（候选集合 -> 小批量高价值 URL）

HIGH_VALUE_PATH_KEYWORDS = [
    "/about",
    "/company",
    "/leadership",
    "/team",
    "/pricing",
    "/plans",
    "/docs",
    "/documentation",
    "/whitepaper",
    "/research",
    "/investor",
    "/ir",
]

LOW_VALUE_PATH_KEYWORDS = [
    "/login",
    "/signin",
    "/signup",
    "/register",
    "/privacy",
    "/terms",
    "/cookie",
    "/cart",
    "/checkout",
]

AUTHORITY_SUFFIXES = [".gov", ".edu"]
AUTHORITY_DOMAINS = {
    "wikipedia.org",
    "who.int",
    "oecd.org",
    "iso.org",
    "ietf.org",
    "w3.org",
    "sec.gov",
    "arxiv.org",
    "nature.com",
    "science.org",
    "crossref.org",
    "openreview.net",
    "aclanthology.org",
    "paperswithcode.com",
    "semanticscholar.org",
}

PAPER_PRIMARY_DOMAINS = {
    "arxiv.org",
    "openreview.net",
    "aclanthology.org",
    "paperswithcode.com",
    "semanticscholar.org",
    "huggingface.co",
    "github.com",
}

LOW_AUTHORITY_OR_DISTRACTION_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "medium.com",
    "dev.to",
    "goml.io",
    "dataforest.ai",
    "towardsdev.com",
}

NEWS_DOMAINS = {
    "reuters.com",
    "bloomberg.com",
    "techcrunch.com",
    "theverge.com",
    "wsj.com",
    "ft.com",
    "nytimes.com",
}

SOCIAL_DOMAINS = {
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "bilibili.com",
}

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
    "training",
    "evidence",
    "fetched",
    "source",
    "sources",
    "paper",
    "papers",
    "technical",
    "report",
}


def _normalize_url(url: str) -> str:
    # 中文注释：URL 归一化，去掉锚点并统一尾斜杠
    if not url:
        return ""
    base = url.split("#", 1)[0].strip()
    if base.endswith("/"):
        return base[:-1]
    return base


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower()


def _path(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.path or "/").lower()


def _is_authoritative_domain(domain: str) -> bool:
    if not domain:
        return False
    if any(domain.endswith(suffix) for suffix in AUTHORITY_SUFFIXES):
        return True
    return any(domain == d or domain.endswith(f".{d}") for d in AUTHORITY_DOMAINS)


def _is_domain_in_set(domain: str, domains: Set[str]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in domains)


def _is_paper_query(query: str) -> bool:
    lowered = (query or "").lower()
    markers = [
        "paper",
        "technical report",
        "arxiv",
        "openreview",
        "llama",
        "qwen",
        "kimi",
        "论文",
        "技术报告",
    ]
    return any(marker in lowered for marker in markers)


def _matches_source_type(domain: str, source_type: str) -> bool:
    source = (source_type or "").strip().lower()
    if source == "official":
        if _is_authoritative_domain(domain):
            return True
        if _is_domain_in_set(domain, SOCIAL_DOMAINS):
            return False
        if _is_domain_in_set(domain, LOW_AUTHORITY_OR_DISTRACTION_DOMAINS):
            return False
        if _is_domain_in_set(domain, NEWS_DOMAINS):
            return False
        if domain.startswith(("discuss.", "forum.", "community.")) or ".discuss." in domain:
            return False
        return bool(domain and "." in domain)
    if source == "aggregator":
        return _is_domain_in_set(
            domain,
            {
                "arxiv.org",
                "wikipedia.org",
                "semanticscholar.org",
                "crossref.org",
                "paperswithcode.com",
                "huggingface.co",
                "openreview.net",
                "github.com",
            },
        )
    if source == "news":
        return _is_domain_in_set(domain, NEWS_DOMAINS)
    if source == "academic":
        return _is_domain_in_set(
            domain,
            {"arxiv.org", "openreview.net", "aclanthology.org", "nature.com", "science.org", "springer.com", "ieee.org"},
        )
    if source == "social":
        return _is_domain_in_set(domain, SOCIAL_DOMAINS)
    if source == "github":
        return _is_domain_in_set(domain, {"github.com", "gitlab.com"})
    if source == "financial":
        return _is_domain_in_set(domain, {"sec.gov", "wsj.com", "ft.com", "bloomberg.com"})
    if source == "local_cn":
        return domain.endswith(".cn")
    if source == "local_jp":
        return domain.endswith(".jp")
    return False


def _path_value_score(path: str) -> float:
    score = 0.0
    if any(key in path for key in HIGH_VALUE_PATH_KEYWORDS):
        score += 0.7
    if any(key in path for key in LOW_VALUE_PATH_KEYWORDS):
        score -= 0.8
    if path in {"", "/"}:
        score += 0.2
    return score


def _query_match_score(query: str, title: str, snippet: str) -> float:
    terms = [t for t in re.split(r"\W+", (query or "").lower()) if t]
    if not terms:
        return 0.0
    text = f"{title} {snippet}".lower()
    hits = sum(1 for term in terms if term and term in text)
    return min(0.6, hits * 0.08)


def _query_focus_terms(query: str, max_terms: int = 8) -> List[str]:
    terms = []
    for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", (query or "").lower()):
        clean = token.strip()
        if len(clean) < 4:
            continue
        if clean in QUERY_NOISE_TERMS:
            continue
        if clean not in terms:
            terms.append(clean)
        if len(terms) >= max_terms:
            break
    return terms


def _domain_matches_query_entity(domain: str, query: str) -> bool:
    focus_terms = _query_focus_terms(query, max_terms=8)
    if not focus_terms:
        return False
    return any(term in domain for term in focus_terms)


def _score_candidate(candidate: Dict[str, Any], query: str) -> Tuple[float, List[str]]:
    url = str(candidate.get("url") or "")
    domain = _domain(url)
    path = _path(url)

    base_score = float(candidate.get("score") or 0.0)
    reasons: List[str] = []
    final_score = base_score

    if _is_authoritative_domain(domain):
        final_score += 1.0
        reasons.append("authoritative_domain")

    if _is_paper_query(query):
        if _is_domain_in_set(domain, PAPER_PRIMARY_DOMAINS):
            final_score += 1.2
            reasons.append("paper_primary_domain")
        if _is_domain_in_set(domain, LOW_AUTHORITY_OR_DISTRACTION_DOMAINS):
            final_score -= 1.3
            reasons.append("paper_low_authority_domain")
    elif _is_domain_in_set(domain, LOW_AUTHORITY_OR_DISTRACTION_DOMAINS):
        final_score -= 0.5
        reasons.append("low_authority_domain")

    pscore = _path_value_score(path)
    if pscore > 0:
        reasons.append("high_information_density_path")
    elif pscore < 0:
        reasons.append("low_value_path")
    final_score += pscore

    qscore = _query_match_score(query, str(candidate.get("title") or ""), str(candidate.get("snippet") or ""))
    if qscore > 0:
        reasons.append("query_term_match")
    final_score += qscore

    if path.count("/") <= 2:
        final_score += 0.1

    return final_score, reasons


def select_candidate_urls(
    query: str,
    candidates: List[Dict[str, Any]],
    max_urls: int = 3,
    seen_urls: Set[str] | None = None,
    required_sources: List[str] | None = None,
    avoid_sources: List[str] | None = None,
) -> List[Dict[str, Any]]:
    # 中文注释：按优先级打分并选出本轮要抓取的 URL（默认 1-3 个）
    seen = seen_urls or set()
    scored: List[Dict[str, Any]] = []

    required = [str(item).strip().lower() for item in (required_sources or []) if str(item).strip()]
    avoid = [str(item).strip().lower() for item in (avoid_sources or []) if str(item).strip()]
    paper_query = _is_paper_query(query)

    for item in candidates or []:
        if not isinstance(item, dict):
            continue
        url = _normalize_url(str(item.get("url") or ""))
        if not url or url in seen:
            continue
        domain = _domain(url)

        # 中文注释：论文检索时收紧来源，避免抓到无关教程/项目管理页面
        if paper_query:
            is_primary_paper_domain = _is_domain_in_set(domain, PAPER_PRIMARY_DOMAINS)
            if not (is_primary_paper_domain or _is_authoritative_domain(domain) or _domain_matches_query_entity(domain, query)):
                continue

        if avoid and any(_matches_source_type(domain, source_type) for source_type in avoid):
            continue
        if required and not any(_matches_source_type(domain, source_type) for source_type in required):
            continue

        score, reasons = _score_candidate(item, query=query)
        enriched = dict(item)
        enriched["url"] = url
        enriched["selector_score"] = round(score, 4)
        enriched["selector_reasons"] = reasons
        scored.append(enriched)

    scored.sort(key=lambda x: float(x.get("selector_score") or 0.0), reverse=True)

    selected: List[Dict[str, Any]] = []
    used_domains: Set[str] = set()
    limit = max(1, min(max_urls, 3))

    # 中文注释：先保证域名多样性，再补足数量
    for item in scored:
        domain = _domain(str(item.get("url", "")))
        if domain and domain in used_domains:
            continue
        selected.append(item)
        if domain:
            used_domains.add(domain)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for item in scored:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) >= limit:
                break

    return selected
