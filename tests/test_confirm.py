from datetime import date, timedelta

from tt_engine.db import models
from tt_engine.detection import confirm_metrics, cross_confirm, evaluate


def _series(units_fn, sellers0, promo0, ads0, ad_age, n=35):
    today = date.today()
    out = []
    u = 40.0
    for i in range(n):
        u = units_fn(u, i, n)
        out.append(models.DailyMetric(
            product_id="X", date=(today - timedelta(days=n - 1 - i)).isoformat(),
            units=int(u), gmv=u * 24.99, price=24.99,
            sellers=int(sellers0 * 1.02 ** i), promo_videos=int(promo0 * 1.04 ** i),
            ads=int(ads0 * 1.05 ** i), avg_ad_age=ad_age,
        ))
    return out


def _accel(u, i, n):
    return u * (1 + (0.02 if i < n * 2 // 3 else 0.16))


def _flat(u, i, n):
    return 12.0


def test_both_sources_confirm():
    a = _series(_accel, 3, 4, 2, 6.0)
    b = _series(_accel, 3, 4, 2, 6.0)
    cc = confirm_metrics(a, b)
    assert cc.confirmed
    assert cc.agreement
    assert "confirmed" in cc.note


def test_disagreement_is_not_confirmed():
    triggered = evaluate(_series(_accel, 3, 4, 2, 6.0))
    flat = evaluate(_series(_flat, 80, 30, 10, 90.0))
    cc = cross_confirm(triggered, flat)
    assert not cc.confirmed
    assert not cc.agreement
    assert "DISAGREE" in cc.note


def test_window_is_conservative_minimum():
    a = evaluate(_series(_accel, 3, 4, 2, 6.0))
    b = evaluate(_series(_accel, 3, 4, 2, 6.0))
    cc = cross_confirm(a, b)
    assert cc.window_days == min(a.window_days, b.window_days)
