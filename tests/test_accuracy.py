"""The accuracy upgrades: spike-resistant momentum, trend consistency, the
review-complaint return-risk signal, and the impulse price band."""

from datetime import date, timedelta

from tt_engine.db import models
from tt_engine.detection import compute_momentum
from tt_engine.detection._stats import despike, trend_consistency
from tt_engine.pipeline import return_rate_for
from tt_engine.psychology import complaint_signal
from tt_engine.scoring.subscores import _price_band


def _metrics(units, price=24.99):
    today = date.today()
    n = len(units)
    return [models.DailyMetric(
        product_id="T", date=(today - timedelta(days=n - 1 - i)).isoformat(),
        units=int(u), gmv=u * price, price=price, sellers=5, promo_videos=10,
        ads=3, avg_ad_age=6.0) for i, u in enumerate(units)]


# ── spike resistance ─────────────────────────────────────────────────────────────
def test_single_viral_day_is_capped():
    flat_with_spike = [50, 52, 48, 51, 49, 50, 900]  # one viral video
    capped = despike(flat_with_spike)
    assert max(capped) == 3 * 50  # capped at 3× median
    m = compute_momentum(_metrics([50] * 28 + flat_with_spike))
    assert m.spike_capped
    # Without the cap velocity_7d would be ~171/day; the trend is really ~64.
    assert m.velocity_7d < 80


def test_genuine_ramp_is_not_capped():
    ramp = [40, 55, 75, 100, 140, 190, 260]  # many rising days — real momentum
    assert despike(ramp) == ramp
    m = compute_momentum(_metrics([30] * 28 + ramp))
    assert not m.spike_capped


# ── trend consistency ────────────────────────────────────────────────────────────
def test_consistency_prefers_steady_growth_over_spikes():
    steady = trend_consistency([40, 46, 53, 61, 70, 80, 92, 106, 122, 140, 161, 185, 213, 245])
    spiky = trend_consistency([50, 48, 52, 700, 49, 51, 47, 50, 52, 48, 650, 51, 49, 50])
    assert steady > 0.8
    assert spiky < 0.3
    assert trend_consistency([1, 2]) == 0.5  # too short → neutral


def test_momentum_carries_consistency():
    m = compute_momentum(_metrics([40 * 1.08 ** i for i in range(30)]))
    assert m.consistency > 0.8


# ── review complaints → return risk ─────────────────────────────────────────────
def test_complaint_signal_density():
    assert complaint_signal([]) == 0.0
    assert complaint_signal(["love it", "amazing"]) == 0.0
    heavy = ["broke after two days, want a refund", "cheap and flimsy, fell apart",
             "poor quality, doesn't work"]
    assert complaint_signal(heavy) >= 0.9


def test_complaints_can_trip_the_return_risk_gate():
    clean = return_rate_for("beauty", ["obsessed", "love it"])
    assert clean == 0.04  # category prior untouched
    complainy = return_rate_for(
        "beauty",
        ["broke immediately, refund please", "cheap flimsy junk, fell apart",
         "doesn't work at all, waste of money"],
    )
    assert complainy >= 0.10  # 4% prior + complaint bump crosses the 10% gate


# ── impulse price band ───────────────────────────────────────────────────────────
def test_price_band_sweet_spot():
    assert _price_band(24.99) == 1.0        # in the $15–50 impulse band
    assert _price_band(15.0) == 1.0 and _price_band(50.0) == 1.0
    assert _price_band(5.0) == 0.0          # can't buy the customer profitably
    assert _price_band(100.0) == 0.0        # scroll-buy reflex is gone
    assert 0 < _price_band(10.0) < 1        # partial credit on the shoulders
    assert 0 < _price_band(70.0) < 1
