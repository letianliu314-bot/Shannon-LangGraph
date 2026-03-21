from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class QualityScoringConfig:
    correctness_weight: float = 0.35
    completeness_weight: float = 0.25
    structure_weight: float = 0.20
    usability_weight: float = 0.20
    pass_threshold: float = 0.80
    warning_threshold: float = 0.65
    correctness_hard_threshold: float = 0.50


def _to_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed


def load_quality_scoring_config(path: str | Path = "config/validation/content_quality.yaml") -> QualityScoringConfig:
    config_path = Path(path)
    if not config_path.exists():
        return QualityScoringConfig()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data: Dict[str, Any] = raw if isinstance(raw, dict) else {}

    weights = data.get("weights") if isinstance(data.get("weights"), dict) else {}
    thresholds = data.get("thresholds") if isinstance(data.get("thresholds"), dict) else {}

    return QualityScoringConfig(
        correctness_weight=_to_float(weights.get("correctness"), 0.35),
        completeness_weight=_to_float(weights.get("completeness"), 0.25),
        structure_weight=_to_float(weights.get("structure"), 0.20),
        usability_weight=_to_float(weights.get("usability"), 0.20),
        pass_threshold=_to_float(thresholds.get("pass"), 0.80),
        warning_threshold=_to_float(thresholds.get("warning"), 0.65),
        correctness_hard_threshold=_to_float(thresholds.get("correctness_hard"), 0.50),
    )