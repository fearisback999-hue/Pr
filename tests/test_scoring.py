from datetime import date, timedelta

from tt_engine.db import models
from tt_engine.detection import evaluate
from tt_engine.economics import compute_economics
from tt_engine.psychology import emotion_signal
from tt_engine.scoring import ContentSignals, ScoringInputs, check_gates, score_product

# Representative strong-emotion review corpus (as the live feed would supply).
_STRONG_REVIEWS = [
    "OMG this melts my tension away, obsessed",
    "the tingles are insane, cannot believe it",
    "everyone asked where I got it",
]


def _trigger():
    n = 35
    units, u = [], 40.0
    for i in range(n):
        u *= 1 + (0.02 if i < 23 else 0.16)
        units.append(u)
    today = date.today()
    metrics = [
        models.DailyMetric(
            product_id="X", date=(today - timedelta(days=n - 1 - i)).isoformat(),
            units=int(units[i]), gmv=units[i] * 24.99, price=24.99,
            sellers=int(3 * 1.02 ** i), promo_videos=int(4 * 1.04 ** i),
            ads=int(2 * 1.05 ** i), avg_ad_age=6.0,
        )
        for i in range(n)
    ]
    return evaluate(metrics)


def _inputs(category="beauty", branded=False, restricted=False, price=24.99,
            cost=6.0, ship=1.5, return_rate=0.04, reviews=None):
    product = models.Product(id="X", name="Test", category=category,
                             branded=branded, restricted=restricted)
    econ = compute_economics(price, cost, ship, return_rate=return_rate)
    content = ContentSignals()
    sig = emotion_signal(reviews if reviews is not None else _STRONG_REVIEWS)
    if sig is not None:
        content.curiosity_interrupt, content.emotional_reaction = sig
    return ScoringInputs(product=product, trigger=_trigger(), economics=econ,
                         search_trend_slope=0.3, content=content)


def test_clean_product_passes_gates_and_scores_in_range():
    b = score_product(_inputs())
    assert b.score.gates_passed
    assert 0 <= b.score.total <= 100
    # category points sum to total
    assert abs(sum(b.category_points.values()) - b.score.total) < 0.1


def test_strong_clean_product_is_recommendable():
    b = score_product(_inputs())
    # A genuinely strong, early, demonstrable, healthy-margin product should clear the bar.
    assert b.score.total >= 80
    assert b.recommended


def test_branded_gate_blocks():
    g = check_gates(_inputs(branded=True))
    assert not g.passed
    assert any("branded" in f for f in g.failures)


def test_restricted_gate_blocks():
    g = check_gates(_inputs(restricted=True))
    assert not g.passed
    assert any("restricted" in f for f in g.failures)


def test_thin_margin_gate_blocks():
    g = check_gates(_inputs(price=6.49, cost=4.5, ship=0.3))
    assert not g.passed
    assert any("margin" in f for f in g.failures)


def test_return_risk_gate_blocks():
    g = check_gates(_inputs(category="apparel", return_rate=0.12))
    assert not g.passed
    assert any("return" in f for f in g.failures)


def test_hot_momentum_cannot_override_economic_landmine():
    """A hot momentum score must never override an economic gate (Part 3)."""
    b = score_product(_inputs(price=6.49, cost=4.5, ship=0.3))
    assert not b.recommended  # blocked regardless of total
