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
    assert result.score == 0.25


def test_per_segment_threshold_and_rainfall_pressure() -> None:
    from app.services.risk_engine import segment_threshold, rainfall_pressure

    # High vulnerability segment (flat/low terrain=0.9, flood_history=0.8)
    t_vulnerable = segment_threshold(0.9, 0.8)
    # T_seg = 30 * (1 - 0.5*0.9 - 0.3*0.8) = 30 * (1 - 0.45 - 0.24) = 30 * 0.31 = 9.3 mm/h
    assert 9.0 <= t_vulnerable <= 9.5

    # Safe segment (hill/high terrain=0.1, no flood history=0.0)
    t_safe = segment_threshold(0.1, 0.0)
    # T_seg = 30 * (1 - 0.5*0.1 - 0.3*0.0) = 30 * 0.95 = 28.5 mm/h
    assert 28.0 <= t_safe <= 29.0

    # 15 mm/h rain should saturate vulnerable road (15/9.3 > 1.0 -> 1.0) but only ~50% for safe road (15/28.5 ~ 0.526)
    p_vuln = rainfall_pressure(15.0, t_vulnerable)
    p_safe = rainfall_pressure(15.0, t_safe)
    assert p_vuln == 1.0
    assert 0.50 <= p_safe <= 0.55

