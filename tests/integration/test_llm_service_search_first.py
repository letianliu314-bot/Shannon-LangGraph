from fastapi.testclient import TestClient

from shannon.llm_service.main import app

# 中文注释：LLM Service Search-first 集成测试


def test_agent_run_returns_retrieval_trace(monkeypatch):
    from shannon.llm_service import main as main_module

    def fake_pipeline(
        query,
        max_rounds=2,
        per_round_fetch_limit=3,
        max_search_results=8,
        domains=None,
        source_guidance=None,
    ):
        return {
            "rounds": [{"round": 1, "query": query, "selected_count": 1}],
            "selected_urls": [{"url": "https://example.com/about", "selector_score": 1.2, "selector_reasons": ["high_information_density_path"]}],
            "fetched_pages": [
                {
                    "url": "https://example.com/about",
                    "status": "ok",
                    "title": "About",
                    "date": "2025-01-01",
                    "author": "Example",
                    "content_hash": "abc",
                    "snippets": ["Example snippet"],
                }
            ],
            "metrics": {"candidate_total": 3, "selected_total": 1, "fetched_total": 1, "quality_passed": True},
        }

    def fake_complete(self, prompt, model, temperature, system_prompt=None):
        return "synthetic summary"

    monkeypatch.setattr(main_module, "run_search_first_pipeline", fake_pipeline)
    monkeypatch.setattr(main_module.OpenAIClient, "complete", fake_complete)

    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "user_request": "研究 Example 公司",
            "strategy": "deep",
            "task": {
                "id": "task-1",
                "title": "Company profile",
                "goal": "Find official profile",
                "deps": [],
                "deliverable": "summary",
                "acceptance_criteria": ["facts"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["web_search", "web_fetch"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["retrieval_trace"]["policy"] == "search_first"
    assert len(payload["citations"]) == 1


def test_agent_run_model_error_not_marked_ok(monkeypatch):
    from shannon.llm_service import main as main_module

    def fake_pipeline(
        query,
        max_rounds=2,
        per_round_fetch_limit=3,
        max_search_results=8,
        domains=None,
        source_guidance=None,
    ):
        return {
            "rounds": [{"round": 1, "query": query, "selected_count": 1}],
            "selected_urls": [{"url": "https://example.com/about", "selector_score": 1.0, "selector_reasons": []}],
            "fetched_pages": [
                {
                    "url": "https://example.com/about",
                    "status": "ok",
                    "title": "About",
                    "date": "2025-01-01",
                    "author": "Example",
                    "content_hash": "abc",
                    "snippets": ["Example snippet"],
                }
            ],
            "metrics": {"candidate_total": 1, "selected_total": 1, "fetched_total": 1, "quality_passed": True},
        }

    def fake_complete(self, prompt, model, temperature, system_prompt=None):
        return "[error:gpt-4o] BadRequestError: invalid parameter"

    monkeypatch.setattr(main_module, "run_search_first_pipeline", fake_pipeline)
    monkeypatch.setattr(main_module.OpenAIClient, "complete", fake_complete)

    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "user_request": "debug query",
            "strategy": "deep",
            "task": {
                "id": "task-1",
                "title": "Test status",
                "goal": "Check status mapping",
                "deps": [],
                "deliverable": "summary",
                "acceptance_criteria": ["facts"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["web_search", "web_fetch"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "model_error"


def test_agent_run_transform_requires_previous_results(monkeypatch):
    from shannon.llm_service import main as main_module

    def fake_complete(self, prompt, model, temperature, system_prompt=None):
        return "should not be called"

    monkeypatch.setattr(main_module.OpenAIClient, "complete", fake_complete)

    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "user_request": "Generate JSONL samples",
            "strategy": "deep",
            "task": {
                "id": "task-4",
                "title": "Generate training samples",
                "goal": "Generate N JSONL-formatted training samples per paper",
                "description": "Generate jsonl output based on abstracts",
                "deps": ["task-3"],
                "deliverable": "structured",
                "acceptance_criteria": ["produces useful output"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["web_search", "web_fetch"],
            },
            "previous_results": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "missing_previous_results"


def test_agent_run_non_transform_soft_degrades_on_low_retrieval_quality(monkeypatch):
    from shannon.llm_service import main as main_module

    def fake_pipeline(
        query,
        max_rounds=2,
        per_round_fetch_limit=3,
        max_search_results=8,
        domains=None,
        source_guidance=None,
    ):
        return {
            "rounds": [{"round": 1, "query": query, "selected_count": 0}],
            "selected_urls": [],
            "fetched_pages": [],
            "metrics": {"candidate_total": 0, "selected_total": 0, "fetched_total": 0, "quality_passed": False},
        }

    def fake_complete(self, prompt, model, temperature, system_prompt=None):
        return "I will continue searching and provide next steps."

    monkeypatch.setattr(main_module, "run_search_first_pipeline", fake_pipeline)
    monkeypatch.setattr(main_module.OpenAIClient, "complete", fake_complete)

    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "user_request": "Research DeepSeek LLM paper",
            "strategy": "deep",
            "task": {
                "id": "task-1",
                "title": "Research DeepSeek",
                "goal": "Collect evidence for DeepSeek LLM",
                "description": "Research DeepSeek paper",
                "deps": [],
                "deliverable": "facts_and_citations",
                "acceptance_criteria": ["contains key findings"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["web_search", "web_fetch"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["quality_status"] == "ok"
    assert "Findings Summary" in payload["content"]
    assert payload["retrieval_trace"].get("warnings")


def test_agent_run_structured_output_fallback_generates_required_fields(monkeypatch):
    from shannon.llm_service import main as main_module

    def fake_complete(self, prompt, model, temperature, system_prompt=None):
        return "not valid structured output"

    monkeypatch.setattr(main_module.OpenAIClient, "complete", fake_complete)

    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "user_request": "Generate exactly 10 JSONL QA samples",
            "strategy": "deep",
            "task": {
                "id": "task-jsonl",
                "title": "Generate JSONL QA",
                "goal": "Generate structured JSONL question-answer training samples",
                "description": "Generate exactly 10 jsonl lines with required fields",
                "deps": ["task-1"],
                "deliverable": "structured_jsonl",
                "acceptance_criteria": ["outputs valid JSONL lines"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["mcp_fetch"],
                "output_format": {
                    "type": "structured",
                    "required_fields": ["line_id", "question", "answer", "source", "difficulty"],
                    "optional_fields": ["transition"],
                },
            },
            "previous_results": {
                "task-1": {
                    "status": "ok",
                    "content": "dep content",
                    "citations": [{"url": "https://arxiv.org/abs/2401.02954"}],
                    "quality_status": "ok",
                    "retrieval_trace": {"policy": "search_first"},
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    lines = [line for line in payload["content"].splitlines() if line.strip()]
    assert len(lines) == 10
    import json as _json

    first = _json.loads(lines[0])
    assert {"line_id", "question", "answer", "source", "difficulty"}.issubset(set(first.keys()))
