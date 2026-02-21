from __future__ import annotations

import hashlib
import html
import io
import ipaddress
import re
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

# 中文注释：检索层 2 - Web Fetch（受控抓取）

USER_AGENT = "ShannonFetcher/1.0 (+https://github.com/Kocoro-lab/Shannon)"


def _is_private_hostname(hostname: str) -> bool:
    # 中文注释：SSRF 防护，阻止私网/本机地址
    if not hostname:
        return True

    lowered = hostname.lower()
    if lowered in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip = ipaddress.ip_address(lowered)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except Exception:  # noqa: BLE001
        pass

    try:
        resolved = socket.gethostbyname(lowered)
        ip = ipaddress.ip_address(resolved)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except Exception:  # noqa: BLE001
        # 中文注释：DNS 异常时保守处理为不可访问
        return True


def _extract_title(html_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def _extract_meta(html_text: str, keys: List[str]) -> str:
    # 中文注释：从 meta 标签中提取 author/date 等字段
    for key in keys:
        pattern = (
            r"<meta[^>]+(?:name|property)=[\"']"
            + re.escape(key)
            + r"[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>"
        )
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
            if value:
                return value
    return ""


def _html_to_text(html_text: str) -> str:
    # 中文注释：简化 HTML 清洗，保留可读正文
    content = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    content = re.sub(r"<style[\s\S]*?</style>", " ", content, flags=re.IGNORECASE)
    content = re.sub(r"<noscript[\s\S]*?</noscript>", " ", content, flags=re.IGNORECASE)
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content)
    content = re.sub(r"\s+", " ", content)
    return content.strip()


def _extract_snippets(text: str, max_snippets: int = 3, snippet_len: int = 280) -> List[str]:
    # 中文注释：抽取可引用片段，供后续综合/验证
    if not text:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+", text)
    snippets: List[str] = []
    for part in parts:
        clean = part.strip()
        if len(clean) < 40:
            continue
        snippets.append(clean[:snippet_len])
        if len(snippets) >= max_snippets:
            break
    if not snippets:
        snippets = [text[:snippet_len]]
    return snippets


def _looks_like_pdf(content_type: str, final_url: str) -> bool:
    content_type_lower = str(content_type or "").lower()
    if "application/pdf" in content_type_lower:
        return True
    path = (urlparse(final_url).path or "").lower()
    return path.endswith(".pdf")


def _extract_pdf_text(pdf_bytes: bytes, max_chars: int) -> Dict[str, Any]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return {"status": "error", "error": "pdf_parser_unavailable"}

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"pdf_open_failed:{type(exc).__name__}"}

    text_parts: List[str] = []
    char_budget = max_chars if max_chars > 0 else 200000
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = ""
        if page_text:
            text_parts.append(page_text)
        if sum(len(part) for part in text_parts) >= char_budget:
            break

    content = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
    if max_chars > 0:
        content = content[:max_chars]
    if not content:
        return {"status": "error", "error": "pdf_no_extractable_text"}

    metadata = reader.metadata or {}
    title = ""
    author = ""
    date = ""
    try:
        title = str(getattr(metadata, "title", "") or metadata.get("/Title") or "").strip()
    except Exception:  # noqa: BLE001
        title = ""
    try:
        author = str(getattr(metadata, "author", "") or metadata.get("/Author") or "").strip()
    except Exception:  # noqa: BLE001
        author = ""
    try:
        date = str(metadata.get("/CreationDate") or "").strip()
    except Exception:  # noqa: BLE001
        date = ""

    return {
        "status": "ok",
        "content": content,
        "title": title,
        "author": author,
        "date": date,
    }


def _fetch_one_url(
    url: str,
    timeout: float,
    max_chars: int,
    include_raw_html: bool,
) -> Dict[str, Any]:
    # 中文注释：抓取单个 URL 并返回结构化元数据
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"url": url, "status": "error", "error": "only http/https supported"}

    hostname = parsed.hostname or ""
    if _is_private_hostname(hostname):
        return {"url": url, "status": "error", "error": "private/internal host blocked"}

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.6",
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            status_code = response.status_code
            if status_code >= 400:
                return {
                    "url": url,
                    "status": "error",
                    "http_status": status_code,
                    "error": f"http_{status_code}",
                }

            content_type = response.headers.get("content-type", "")
            final_url = str(response.url)
            text_content = ""
            title = ""
            author = ""
            date = ""
            body = ""

            if _looks_like_pdf(content_type, final_url):
                pdf_result = _extract_pdf_text(response.content, max_chars=max_chars)
                if pdf_result.get("status") != "ok":
                    return {
                        "url": final_url,
                        "source_url": url,
                        "status": "error",
                        "http_status": status_code,
                        "content_type": content_type,
                        "error": str(pdf_result.get("error") or "pdf_parse_failed"),
                    }
                text_content = str(pdf_result.get("content") or "")
                title = str(pdf_result.get("title") or "")
                author = str(pdf_result.get("author") or "")
                date = str(pdf_result.get("date") or "")
            else:
                body = response.text
                if not body:
                    return {"url": final_url, "status": "error", "error": "empty_content", "http_status": status_code}

                title = _extract_title(body)
                author = _extract_meta(body, ["author", "article:author", "og:author"])
                date = _extract_meta(
                    body,
                    [
                        "article:published_time",
                        "date",
                        "publishdate",
                        "pubdate",
                        "last-modified",
                    ],
                )

                text_content = _html_to_text(body)
                if max_chars > 0:
                    text_content = text_content[:max_chars]

            content_hash = hashlib.sha256(text_content.encode("utf-8", errors="ignore")).hexdigest()
            snippets = _extract_snippets(text_content)

            result: Dict[str, Any] = {
                "url": final_url,
                "source_url": url,
                "status": "ok",
                "http_status": status_code,
                "content_type": content_type,
                "title": title,
                "date": date,
                "author": author,
                "content": text_content,
                "snippets": snippets,
                "content_hash": content_hash,
            }
            if include_raw_html:
                result["raw_html"] = body
            return result
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "status": "error",
            "error": f"{type(exc).__name__}:{str(exc)[:160]}",
        }


def web_fetch(
    urls: List[str],
    timeout: float = 15.0,
    max_chars: int = 12000,
    include_raw_html: bool = False,
) -> List[Dict[str, Any]]:
    # 中文注释：批量抓取 URL，输出可引用片段 + 元数据
    normalized_urls = []
    for url in urls or []:
        if not isinstance(url, str):
            continue
        cleaned = url.strip()
        if cleaned:
            normalized_urls.append(cleaned)

    results: List[Dict[str, Any]] = []
    for url in normalized_urls:
        results.append(
            _fetch_one_url(
                url=url,
                timeout=timeout,
                max_chars=max_chars,
                include_raw_html=include_raw_html,
            )
        )
    return results
