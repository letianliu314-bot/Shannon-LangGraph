from shannon.llm_service.client.openai_client import OpenAIClient

# 中文注释：LLM Service 客户端测试


def test_openai_client_stub(monkeypatch):
    monkeypatch.setattr("shannon.llm_service.client.openai_client.find_dotenv", lambda usecwd=True: "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = OpenAIClient()
    content = client.complete("hello", model="gpt-test", temperature=0.1)
    assert content


def test_openai_client_omit_temperature_for_gpt5_nano(monkeypatch):
    class _FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return type(
                "Resp",
                (),
                {"choices": [type("Choice", (), {"message": type("Msg", (), {"content": "ok"})()})()]},
            )()

    fake_completions = _FakeCompletions()
    fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": fake_completions})()})()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAIClient()
    client._sdk_client = fake_client

    content = client.complete("hello", model="gpt-5-nano", temperature=0.2)
    assert content == "ok"
    assert len(fake_completions.calls) == 1
    assert "temperature" not in fake_completions.calls[0]


def test_openai_client_retry_without_temperature_when_unsupported(monkeypatch):
    class _FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise RuntimeError("Unsupported value: 'temperature' does not support 0.2 with this model. Only the default")
            return type(
                "Resp",
                (),
                {"choices": [type("Choice", (), {"message": type("Msg", (), {"content": "retried-ok"})()})()]},
            )()

    fake_completions = _FakeCompletions()
    fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": fake_completions})()})()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAIClient()
    client._sdk_client = fake_client

    content = client.complete("hello", model="gpt-5-mini", temperature=0.2)
    assert content == "retried-ok"
    assert len(fake_completions.calls) == 2
    assert fake_completions.calls[0]["temperature"] == 0.2
    assert "temperature" not in fake_completions.calls[1]
