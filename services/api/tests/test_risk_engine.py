from app.services.risk_engine import calculate_risk


def test_more_rain_never_decreases_risk() -> None:
    base = {"terrain": 0.4, "rainfall": 0.1, "flood_history": 0.3, "drainage": 0.2}
    wet = {**base, "rainfall": 0.9}
    assert calculate_risk(wet).score >= calculate_risk(base).score


def test_dry_day_guardrail_caps_unverified_score() -> None:
    result = calculate_risk(
        {"terrain": 1, "rainfall": 0, "flood_history": 1, "drainage": 1, "citizen_reports": 0},
        is_dry_day=True,
    )
    assert result.score == 0.45
