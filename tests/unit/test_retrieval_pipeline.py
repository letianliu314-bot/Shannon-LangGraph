from shannon.llm_service.retrieval.pipeline import run_search_first_pipeline
from shannon.llm_service.retrieval.selector import select_candidate_urls
from shannon.llm_service.retrieval import fetcher as fetcher_module

# 中文注释：Search-first 检索流程测试


def test_select_candidate_urls_prioritizes_authority_and_density():
    candidates = [
        {"url": "https://example.com/login", "title": "Login", "snippet": "Sign in", "score": 0.9},
        {"url": "https://sec.gov/company/abc", "title": "ABC filing", "snippet": "official filing", "score": 0.3},
        {"url": "https://foo.ai/pricing", "title": "Pricing", "snippet": "plans", "score": 0.2},
    ]

    selected = select_candidate_urls(query="ABC company profile pricing", candidates=candidates, max_urls=2)

    assert len(selected) == 2
    assert selected[0]["url"].startswith("https://sec.gov")


def test_select_candidate_urls_enforces_source_guidance_required_and_avoid():
    candidates = [
        {"url": "https://arxiv.org/abs/2407.10671", "title": "Qwen2", "snippet": "technical report", "score": 0.4},
        {"url": "https://youtube.com/watch?v=abc", "title": "video", "snippet": "summary", "score": 0.9},
        {"url": "https://medium.com/some-post", "title": "blog", "snippet": "thoughts", "score": 0.7},
    ]

    selected = select_candidate_urls(
        query="Qwen2 technical report paper",
        candidates=candidates,
        max_urls=3,
        required_sources=["aggregator", "official"],
        avoid_sources=["social"],
    )

    assert len(selected) == 1
    assert selected[0]["url"] == "https://arxiv.org/abs/2407.10671"


def test_select_candidate_urls_filters_irrelevant_domains_for_paper_query():
    candidates = [
        {
            "url": "https://ecssria.eu/2026_2.3",
            "title": "Architecture and Design: Method And Tools",
            "snippet": "task dependencies and architecture",
            "score": 0.9,
        },
        {
            "url": "https://arxiv.org/abs/2401.02954",
            "title": "DeepSeek LLM",
            "snippet": "Scaling Open-Source Language Models with Longtermism",
            "score": 0.4,
        },
    ]

    selected = select_candidate_urls(
        query="DeepSeek LLM technical report paper",
        candidates=candidates,
        max_urls=2,
        required_sources=["official", "aggregator"],
    )

    assert len(selected) == 1
    assert selected[0]["url"] == "https://arxiv.org/abs/2401.02954"


def test_run_search_first_pipeline_with_mock(monkeypatch):
    # 中文注释：通过 mock 固定 search/fetch/crawl 行为，验证流程聚合结构
    from shannon.llm_service.retrieval import pipeline as pipeline_module

    def fake_search(query, max_results=8, domains=None):
        return [
            {
                "url": "https://official.example.com/about",
                "title": "About",
                "snippet": "Company profile",
                "score": 0.6,
            }
        ]

    def fake_fetch(urls, timeout=15.0, max_chars=12000, include_raw_html=False):
        if not urls:
            return []
        return [
            {
                "url": urls[0],
                "status": "ok",
                "title": "About",
                "date": "2025-01-01",
                "author": "Team",
                "content": "test query company profile " * 80,
                "snippets": ["snippet-a"],
                "content_hash": "hash-a",
            }
        ]

    def fake_crawl(seed_urls, max_pages_per_seed=2, max_total_pages=6, max_chars=10000):
        return {
            "pages": [
                {
                    "url": "https://official.example.com/pricing",
                    "status": "ok",
                    "title": "Pricing",
                    "date": "2025-01-01",
                    "author": "Team",
                    "content": "test query pricing plans " * 90,
                    "snippets": ["snippet-b"],
                    "content_hash": "hash-b",
                }
            ],
            "metadata": {"total_crawled": 1},
        }

    monkeypatch.setattr(pipeline_module, "web_search", fake_search)
    monkeypatch.setattr(pipeline_module, "web_fetch", fake_fetch)
    monkeypatch.setattr(pipeline_module, "web_crawl", fake_crawl)

    result = run_search_first_pipeline("test query", max_rounds=2, per_round_fetch_limit=2, max_search_results=5)

    assert result["metrics"]["selected_total"] >= 1
    assert result["metrics"]["fetched_total"] >= 2
    assert result["metrics"]["quality_passed"] is True


def test_run_search_first_pipeline_passes_source_guidance(monkeypatch):
    from shannon.llm_service.retrieval import pipeline as pipeline_module

    def fake_search(query, max_results=8, domains=None):
        return [
            {"url": "https://arxiv.org/abs/2407.10671", "title": "Qwen2", "snippet": "report", "score": 0.5},
            {"url": "https://youtube.com/watch?v=abc", "title": "video", "snippet": "review", "score": 0.9},
        ]

    def fake_select(query, candidates, max_urls=3, seen_urls=None, required_sources=None, avoid_sources=None):
        assert required_sources == ["official", "aggregator"]
        assert avoid_sources == ["social"]
        return [candidates[0]]

    def fake_fetch(urls, timeout=15.0, max_chars=12000, include_raw_html=False):
        return [
            {
                "url": urls[0],
                "status": "ok",
                "title": "Qwen2",
                "date": "2024-01-01",
                "author": "Qwen Team",
                "content": "qwen2 technical report " * 120,
                "snippets": ["qwen2 technical report"],
                "content_hash": "hash-qwen2",
            }
        ]

    monkeypatch.setattr(pipeline_module, "web_search", fake_search)
    monkeypatch.setattr(pipeline_module, "select_candidate_urls", fake_select)
    monkeypatch.setattr(pipeline_module, "web_fetch", fake_fetch)
    monkeypatch.setattr(pipeline_module, "web_crawl", lambda *args, **kwargs: {"pages": [], "metadata": {}})

    result = run_search_first_pipeline(
        "Qwen2 technical report",
        source_guidance={"required": ["official", "aggregator"], "avoid": ["social"]},
    )
    assert result["metrics"]["required_sources"] == ["official", "aggregator"]
    assert result["metrics"]["avoid_sources"] == ["social"]


def test_web_fetch_pdf_uses_pdf_extractor(monkeypatch):
    class FakeResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "application/pdf"}
            self.content = b"%PDF-1.7 fake"
            self.url = "https://arxiv.org/pdf/2407.10671.pdf"
            self.text = ""

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(fetcher_module, "_is_private_hostname", lambda hostname: False)
    monkeypatch.setattr(fetcher_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        fetcher_module,
        "_extract_pdf_text",
        lambda pdf_bytes, max_chars: {
            "status": "ok",
            "content": "Qwen2 technical report content.",
            "title": "Qwen2 Technical Report",
            "author": "Qwen Team",
            "date": "2024",
        },
    )

    results = fetcher_module.web_fetch(["https://arxiv.org/pdf/2407.10671.pdf"])
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["title"] == "Qwen2 Technical Report"
    assert "Qwen2 technical report content." in results[0]["content"]
    assert results[0]["snippets"]


def test_web_fetch_pdf_parse_failure_returns_error(monkeypatch):
    class FakeResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "application/pdf"}
            self.content = b"%PDF-1.7 broken"
            self.url = "https://arxiv.org/pdf/2507.20534.pdf"
            self.text = ""

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(fetcher_module, "_is_private_hostname", lambda hostname: False)
    monkeypatch.setattr(fetcher_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        fetcher_module,
        "_extract_pdf_text",
        lambda pdf_bytes, max_chars: {"status": "error", "error": "pdf_parse_failed"},
    )

    results = fetcher_module.web_fetch(["https://arxiv.org/pdf/2507.20534.pdf"])
    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert results[0]["error"] == "pdf_parse_failed"
