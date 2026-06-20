from datetime import date, timedelta

from tt_engine.db import models
from tt_engine.detection import compute_momentum, compute_saturation, evaluate
from tt_engine.detection.trigger import MAX_WINDOW_DAYS


def _series(units, sellers, promos, ads, ad_age, price=24.99, n=None):
    """Build n daily metrics ending today. Scalars are broadcast to constant series."""
    n = n or len(units)
    def col(x):
        return x if isinstance(x, list) else [x] * n
    units, sellers, promos, ads, ad_age = map(col, (units, sellers, promos, ads, ad_age))
    today = date.today()
    out = []
    for i in range(n):
        d = (today - timedelta(days=n - 1 - i)).isoformat()
        out.append(models.DailyMetric(
            product_id="T", date=d, units=int(units[i]), gmv=units[i] * price, price=price,
            sellers=int(sellers[i]), promo_videos=int(promos[i]), ads=int(ads[i]),
            avg_ad_age=float(ad_age[i]),
        ))
    return out


def _accelerating(n=35, base=40.0, early=0.02, late=0.16):
    units, u = [], base
    for i in range(n):
        u *= 1 + (early if i < n * 2 // 3 else late)
        units.append(u)
    return units


def test_rising_star_triggers():
    n = 35
    metrics = _series(
        units=_accelerating(n),
        sellers=[3 * (1.02 ** i) for i in range(n)],
        promos=[4 * (1.04 ** i) for i in range(n)],
        ads=[2 * (1.05 ** i) for i in range(n)],
        ad_age=6.0, n=n,
    )
    res = evaluate(metrics)
    assert res.triggered, res.reasons
    assert res.momentum.is_accelerating
    assert res.saturation.index < 55
    assert 0 < res.window_days <= MAX_WINDOW_DAYS


def test_peaked_does_not_trigger():
    n = 35
    # High but flat/declining sales, crowded market, stale ads.
    units = [300 * (0.99 ** i) for i in range(n)]
    metrics = _series(
        units=units,
        sellers=[40 * (1.05 ** i) for i in range(n)],
        promos=[120 * (1.06 ** i) for i in range(n)],
        ads=[60 * (1.05 ** i) for i in range(n)],
        ad_age=55.0, n=n,
    )
    res = evaluate(metrics)
    assert not res.triggered
    assert res.saturation.index > 55


def test_flat_dud_does_not_trigger():
    metrics = _series(units=12, sellers=80, promos=30, ads=10, ad_age=90.0, n=35)
    res = evaluate(metrics)
    assert not res.triggered
    assert not res.momentum.is_accelerating


def test_momentum_ratio_above_one_when_accelerating():
    metrics = _series(units=_accelerating(35), sellers=5, promos=5, ads=3, ad_age=6.0, n=35)
    m = compute_momentum(metrics)
    assert m.velocity_7d > m.velocity_30d
    assert m.momentum_ratio > 1.0


def test_saturation_entrant_rate_positive_when_competition_grows():
    n = 30
    metrics = _series(
        units=50, sellers=[5 * (1.03 ** i) for i in range(n)],
        promos=[5 * (1.03 ** i) for i in range(n)], ads=[3 * (1.03 ** i) for i in range(n)],
        ad_age=8.0, n=n,
    )
    s = compute_saturation(metrics)
    assert s.entrant_rate > 0
