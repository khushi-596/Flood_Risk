"""Transparent baseline flood-risk model used before any learned model is introduced."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml

from app.core.config import get_settings

SIGNALS = ("terrain", "rainfall", "flood_history", "drainage", "citizen_reports")
REASON_LABELS = {
    "terrain": "low-lying or flat terrain",
    "rainfall": "rainfall above the local threshold",
    "flood_history": "a historic flood hotspot",
    "drainage": "limited drainage clearance",
    "citizen_reports": "verified nearby public reports",
}


@dataclass(frozen=True)
class RiskResult:
    score: float
    confidence: float
    band: str
    reasons: list[str]


@lru_cache
def load_model_config(path: Path | None = None) -> Mapping:
    config_path = path or get_settings().model_config
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def calculate_risk(signals: Mapping[str, float], is_dry_day: bool = False) -> RiskResult:
    """Score normalised signals and expose the weighted contributors for the UI."""
    config = load_model_config()
    weights = config["weights"]
    missing = config["defaults"]["missing_signal"]
    normalised = {name: max(0.0, min(1.0, float(signals.get(name, missing)))) for name in SIGNALS}
    contributions = {name: normalised[name] * weights[name] for name in SIGNALS}
    score = sum(contributions.values())

    if is_dry_day and normalised["citizen_reports"] == 0:
        score = min(score, config["guardrails"]["dry_day_score_cap_without_verified_report"])

    bands = config["bands"]
    band = next(name.removesuffix("_max") for name, maximum in bands.items() if score <= maximum)
    observed = sum(name in signals for name in SIGNALS)
    baseline = config["defaults"]["confidence_without_observed_rainfall"]
    confidence = baseline + (config["defaults"]["confidence_with_all_signals"] - baseline) * (observed / len(SIGNALS))
    top_count = config["guardrails"]["top_reason_count"]
    reasons = [REASON_LABELS[name] for name, _ in sorted(contributions.items(), key=lambda item: item[1], reverse=True)[:top_count] if contributions[name] > 0]

    return RiskResult(
        score=round(score, 3),
        confidence=round(confidence, 3),
        band=band,
        reasons=reasons or ["no active flood-risk signals"],
    )


def weighted_contributions(signals: Mapping[str, float]) -> dict[str, float]:
    """Expose the calculation terms without hiding the model behind a black box."""
    weights = load_model_config()["weights"]
    return {
        name: round(max(0.0, min(1.0, float(signals.get(name, 0.0)))) * weights[name], 3)
        for name in SIGNALS
    }


@lru_cache
def load_vehicle_limits() -> Mapping:
    path = get_settings().model_config.parent / "vehicle_limits.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["vehicles"]
