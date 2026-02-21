from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Dict

import yaml

# 中文注释：模型层级与具体模型映射


class ModelTier(str, Enum):
    # 中文注释：小模型档
    SMALL = "small"
    # 中文注释：中模型档
    MEDIUM = "medium"
    # 中文注释：大模型档
    LARGE = "large"


DEFAULT_TIER_TO_OPENAI_MODEL = {
    ModelTier.SMALL: "gpt-5-nano",
    ModelTier.MEDIUM: "gpt-5-mini",
    ModelTier.LARGE: "gpt-5.1",
}


def _default_models_config_path() -> Path:
    # 中文注释：默认读取仓库根目录 config/models.yaml，可被环境变量覆盖
    configured_path = os.getenv("SHANNON_MODELS_CONFIG", "").strip()
    if configured_path:
        return Path(configured_path).expanduser()
    return Path(__file__).resolve().parents[3] / "config" / "models.yaml"


def _pick_openai_model(tier_config: object) -> str | None:
    # 中文注释：从 tier 配置中提取首个 openai 模型
    if not isinstance(tier_config, dict):
        return None
    providers = tier_config.get("providers")
    if not isinstance(providers, list):
        return None
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip().lower()
        model = str(item.get("model") or "").strip()
        if not model:
            continue
        if provider in {"", "openai"}:
            return model
    return None


def _load_tier_to_openai_model() -> Dict[ModelTier, str]:
    # 中文注释：读取 models.yaml，失败时回退默认映射
    mapping = dict(DEFAULT_TIER_TO_OPENAI_MODEL)
    config_path = _default_models_config_path()
    if not config_path.exists():
        return mapping

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return mapping

    if not isinstance(data, dict):
        return mapping
    model_tiers = data.get("model_tiers")
    if not isinstance(model_tiers, dict):
        return mapping

    for tier in ModelTier:
        chosen = _pick_openai_model(model_tiers.get(tier.value))
        if chosen:
            mapping[tier] = chosen
    return mapping


TIER_TO_OPENAI_MODEL = _load_tier_to_openai_model()


# 中文注释：函数 resolve_model 的入口

def resolve_model(model_tier: str | None, model: str | None = None) -> str:
    # 中文注释：若显式指定模型则优先使用
    if model:
        return model

    # 中文注释：默认回退 small；未知 tier 也回退 small
    raw_tier = (model_tier or ModelTier.SMALL.value).lower()
    valid_tiers = {tier.value for tier in ModelTier}
    tier = ModelTier.SMALL if raw_tier not in valid_tiers else ModelTier(raw_tier)
    return TIER_TO_OPENAI_MODEL[tier]
