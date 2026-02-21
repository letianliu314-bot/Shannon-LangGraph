from shannon.orchestration.orchestrator.llm_service_client import LLMServiceClient


def test_responses_timeout_uses_higher_default(monkeypatch):
    monkeypatch.delenv("ORCH_LLM_SERVICE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS", raising=False)

    client = LLMServiceClient(base_url="http://127.0.0.1:8001", timeout=120.0, max_retries=0)
    assert client._resolve_timeout("/agent/run", None) == 120.0
    assert client._resolve_timeout("/v1/responses", None) == 300.0


def test_responses_timeout_honors_env_override(monkeypatch):
    monkeypatch.setenv("ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS", "420")
    client = LLMServiceClient(base_url="http://127.0.0.1:8001", timeout=120.0, max_retries=0)
    assert client._resolve_timeout("/v1/responses", None) == 420.0
