"""Transparent baseline flood-risk model with per-segment rainfall thresholds.

Formula: R = w_s*S + w_r*R_pressure + w_h*H + w_d*D + w_c*C
Per-segment threshold: T_seg = T0 * (1 - 0.5*S - 0.3*H)
Rainfall pressure: R_pressure = min(1.0, rainfall_mm_hr / T_seg)
"""

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


def segment_threshold(terrain_signal: float, flood_history_signal: float) -> float:
    """Per-segment rainfall threshold: T_seg = T0 * (1 - 0.5*S - 0.3*H).

    Lower terrain and higher flood history make a segment more sensitive
    to rainfall, so T_seg drops and the rainfall pressure signal rises
    even under moderate rain.
    """
    config = load_model_config()
    t0 = config["defaults"]["base_threshold_mm_hr"]
    t_seg = t0 * (1.0 - 0.5 * terrain_signal - 0.3 * flood_history_signal)
    # Floor at 5 mm/h so we never divide by near-zero
    return max(5.0, t_seg)


def rainfall_pressure(rainfall_mm_hr: float, t_seg: float) -> float:
    """Normalised rainfall pressure relative to this segment's threshold."""
    return round(min(1.0, max(0.0, rainfall_mm_hr / t_seg)), 3)


def calculate_risk(
    signals: Mapping[str, float],
    is_dry_day: bool = False,
    rainfall_mm_hr: float | None = None,
) -> RiskResult:
    """Score normalised signals and expose the weighted contributors for the UI.

    If rainfall_mm_hr is provided, the rainfall signal is recalculated using
    the per-segment threshold formula.  Otherwise the pre-normalised
    signals['rainfall'] value is used directly.
    """
    config = load_model_config()
    weights = config["weights"]
    missing = config["defaults"]["missing_signal"]

    normalised = {
        name: max(0.0, min(1.0, float(signals.get(name, missing))))
        for name in SIGNALS
    }

    # Per-segment rainfall pressure when raw mm/hr is available
    if rainfall_mm_hr is not None:
        t_seg = segment_threshold(
            normalised["terrain"], normalised["flood_history"]
        )
        normalised["rainfall"] = rainfall_pressure(rainfall_mm_hr, t_seg)

    contributions = {name: normalised[name] * weights[name] for name in SIGNALS}
    score = sum(contributions.values())

    # Dry-day guardrail: cap risk when there is no rain and no crowd evidence
    if is_dry_day and normalised["citizen_reports"] == 0:
        score = min(
            score,
            config["guardrails"]["dry_day_score_cap_without_verified_report"],
        )

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    bands = config["bands"]
    band = next(
        name.removesuffix("_max")
        for name, maximum in bands.items()
        if score <= maximum
    )

    observed = sum(name in signals for name in SIGNALS)
    baseline = config["defaults"]["confidence_without_observed_rainfall"]
    confidence = baseline + (
        config["defaults"]["confidence_with_all_signals"] - baseline
    ) * (observed / len(SIGNALS))

    top_count = config["guardrails"]["top_reason_count"]
    reasons = [
        REASON_LABELS[name]
        for name, _ in sorted(
            contributions.items(), key=lambda item: item[1], reverse=True
        )[:top_count]
        if contributions[name] > 0
    ]

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
        name: round(
            max(0.0, min(1.0, float(signals.get(name, 0.0)))) * weights[name], 3
        )
        for name in SIGNALS
    }


@lru_cache
def load_vehicle_limits() -> Mapping:
    path = get_settings().model_config.parent / "vehicle_limits.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["vehicles"]
