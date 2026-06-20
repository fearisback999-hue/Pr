from tt_engine.account import SUSPENSION_THRESHOLD, THROTTLE_THRESHOLD, assess_health


def test_healthy_account_scores_high():
    h = assess_health(ship_days=3, refund_rate=0.02, response_hrs=6)
    assert h.score >= THROTTLE_THRESHOLD
    assert not h.at_risk
    assert not h.critical


def test_throttle_band_is_at_risk_but_not_critical():
    # Middling on every lever → lands in the throttle band (reach throttled, not suspended).
    h = assess_health(ship_days=6, refund_rate=0.06, response_hrs=20)
    assert h.at_risk and not h.critical
    assert SUSPENSION_THRESHOLD <= h.score < THROTTLE_THRESHOLD
    assert any("throttled" in w for w in h.warnings)


def test_high_refunds_trigger_the_refund_warning():
    h = assess_health(ship_days=4, refund_rate=0.12, response_hrs=8)
    # Refund warning must fire on its own merit (≥ 10%), not piggyback on another message.
    assert any(w.startswith("refund rate") for w in h.warnings)


def test_slow_shipping_warns():
    h = assess_health(ship_days=12, refund_rate=0.03, response_hrs=8)
    assert any(w.startswith("ship time") for w in h.warnings)


def test_critical_account_warns_about_suspension():
    h = assess_health(ship_days=20, refund_rate=0.20, response_hrs=72)
    assert h.critical
    assert h.score < SUSPENSION_THRESHOLD
    assert any("suspension" in w.lower() for w in h.warnings)


def test_levers_are_normalized():
    h = assess_health(ship_days=3, refund_rate=0.0, response_hrs=0)
    assert 0.99 <= h.shipping_score <= 1.0
    assert h.refund_score == 1.0
    assert h.service_score == 1.0
