import importlib


def test_resolve_model_with_default_tiers():
    from shannon.llm_service.provider_manager import resolve_model

    assert resolve_model("small") == "gpt-5-nano"
    assert resolve_model("medium") == "gpt-5-mini"
    assert resolve_model("large") == "gpt-5.1"


def test_resolve_model_fallback_and_override():
    from shannon.llm_service.provider_manager import resolve_model

    assert resolve_model("unknown-tier") == "gpt-5-nano"
    assert resolve_model(None, model="gpt-4.1") == "gpt-4.1"


def test_resolve_model_uses_models_yaml_override(monkeypatch, tmp_path):
    custom_config = tmp_path / "models.yaml"
    custom_config.write_text(
        """
model_tiers:
  small:
    providers:
      - provider: openai
        model: gpt-custom-small
  medium:
    providers:
      - provider: openai
        model: gpt-custom-medium
  large:
    providers:
      - provider: anthropic
        model: claude-not-used
""".strip()
        + "\n",
        encoding="utf-8",
    )

    import shannon.llm_service.provider_manager as provider_manager

    monkeypatch.setenv("SHANNON_MODELS_CONFIG", str(custom_config))
    importlib.reload(provider_manager)
    assert provider_manager.resolve_model("small") == "gpt-custom-small"
    assert provider_manager.resolve_model("medium") == "gpt-custom-medium"
    # large 未配置 openai 时回退默认值
    assert provider_manager.resolve_model("large") == "gpt-5.1"

    monkeypatch.delenv("SHANNON_MODELS_CONFIG", raising=False)
    importlib.reload(provider_manager)
