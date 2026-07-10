"""The six sub-scores (Part 3). Each returns a fraction in [0,1] of its category plus a
component breakdown (for the report). Category weights live in weights.json so the
feedback loop (Part 13) can recalibrate what actually predicted your winners."""

from __future__ import annotations

import math

from ..detection._stats import clamp
from .inputs import ScoringInputs

# Category heuristic profiles — used where a real vision/LLM/trend signal isn't supplied.
# (consumable, ugc_fit, ai_video_fit, category_momentum, line_extension, identity), each 0..1.
_CATEGORY = {
    "beauty":      (0.8, 0.9, 0.8, 0.7, 0.8, 0.7),
    "wellness":    (0.8, 0.8, 0.7, 0.7, 0.7, 0.6),
    "supplement":  (0.9, 0.7, 0.5, 0.7, 0.8, 0.6),
    "apparel":     (0.4, 0.8, 0.7, 0.6, 0.7, 0.8),
    "toys":        (0.5, 0.8, 0.8, 0.6, 0.6, 0.6),
    "electronics": (0.3, 0.6, 0.6, 0.5, 0.5, 0.4),
    "home":        (0.5, 0.7, 0.7, 0.5, 0.6, 0.5),
    "pet":         (0.6, 0.8, 0.7, 0.6, 0.7, 0.8),   # passionate niche audience
    "hobby":       (0.5, 0.8, 0.7, 0.6, 0.7, 0.9),   # identity-driven, low competition
    "accessories": (0.4, 0.8, 0.8, 0.6, 0.7, 0.8),   # aesthetic / self-expression
}
_DEFAULT_PROFILE = (0.5, 0.6, 0.6, 0.5, 0.5, 0.5)

# How commodity a category is by nature — 1 = generic race-to-the-bottom (anyone sources
# the same item from the same suppliers), 0 = inherently differentiable / niche. This is
# the structural half of the differentiation score; the review language is the other half.
_COMMODITY_PRIOR = {
    "electronics": 0.75, "home": 0.55, "toys": 0.45, "apparel": 0.40, "beauty": 0.45,
    "wellness": 0.40, "supplement": 0.35, "pet": 0.20, "hobby": 0.15, "accessories": 0.30,
}
_DEFAULT_COMMODITY_PRIOR = 0.5


def _profile(category: str):
    return _CATEGORY.get(category.lower(), _DEFAULT_PROFILE)


def _weighted(components: dict[str, tuple[float, float]]) -> tuple[float, dict[str, float]]:
    """components: name -> (fraction0..1, subweight). Returns (overall_fraction, points_breakdown)."""
    total_w = sum(w for _, w in components.values())
    breakdown = {name: round(frac * w, 2) for name, (frac, w) in components.items()}
    overall = sum(frac * w for frac, w in components.values()) / total_w if total_w else 0.0
    return overall, breakdown


# ── 1. Viral Demonstration Ability (20): clarity 8, curiosity 4, result 5, emotion 3 ──
def viral_demo(inp: ScoringInputs) -> tuple[float, dict[str, float]]:
    cs = inp.content
    cons, ugc, ai, *_ = _profile(inp.product.category)
    # Heuristic priors when no vision pass is supplied: demonstrable categories (high AI/UGC
    # fit) read well in 3 seconds and show a visible result. Override with ContentSignals.
    clarity = cs.three_second_clarity if cs.three_second_clarity is not None else 0.60 + 0.25 * ai
    curiosity = cs.curiosity_interrupt if cs.curiosity_interrupt is not None else 0.55
    result = cs.visible_result if cs.visible_result is not None else 0.50 + 0.30 * ai
    emotion = cs.emotional_reaction if cs.emotional_reaction is not None else 0.55
    return _weighted({
        "clarity_3s": (clamp(clarity, 0, 1), 8),
        "curiosity": (clamp(curiosity, 0, 1), 4),
        "visible_result": (clamp(result, 0, 1), 5),
        "emotional_reaction": (clamp(emotion, 0, 1), 3),
    })


# ── 2. Market Demand (20): velocity 8, accel 5, trend 3, consistency 2, urgency 2 ──
def market_demand(inp: ScoringInputs) -> tuple[float, dict[str, float]]:
    m = inp.trigger.momentum
    # velocity on a log scale: ~500 units/day → full marks.
    velocity = clamp(math.log10(m.velocity_7d + 1) / math.log10(500), 0, 1)
    accel = clamp(m.wow_growth / 0.5, 0, 1)  # +50% WoW → full
    slope = inp.search_trend_slope
    trend = clamp(0.5 + slope, 0, 1) if slope is not None else 0.5
    urgency = inp.urgency_signal if inp.urgency_signal is not None else _profile(inp.product.category)[0]
    return _weighted({
        "sales_velocity": (velocity, 8),
        "wow_acceleration": (accel, 5),
        "search_trend": (trend, 3),
        # Steady multi-day growth predicts a real wave; a spiky average predicts a
        # one-video flash. Computed from the last 14 days vs their own trend line.
        "trend_consistency": (clamp(m.consistency, 0, 1), 2),
        "urgency_repeat": (clamp(urgency, 0, 1), 2),
    })


# ── 3. Competition Timing (15): saturation⁻¹ 6, window 3, differentiation 4, cat-mom 2 ──
def _differentiation(inp: ScoringInputs) -> float:
    """How defensible / hard-to-copy the product is — the niche-vs-commodity axis.

    A generic commodity (phone stand, USB cable, me-too tumbler) has low differentiation:
    anyone sources the same item and races the price to the bottom, so even a currently
    low-competition commodity gets flooded the moment it works. A niche find (a specific
    hobby tool, a problem-specific pet product, an aesthetic accessory) is harder to copy
    and holds its window. Distinct from saturation, which is only how crowded it is *now*.
    """
    if inp.differentiation is not None:
        return clamp(inp.differentiation, 0, 1)
    commodity_prior = _COMMODITY_PRIOR.get(inp.product.category.lower(),
                                           _DEFAULT_COMMODITY_PRIOR)
    # The corpus can override the category prior upward (reviews screaming 'everyone sells
    # this') but not below it — commoditization language only ever makes it look more generic.
    commodity = max(commodity_prior, clamp(inp.commodity_signal, 0, 1))
    # Rock-bottom price is a race-to-the-bottom tell: <$12 strong, $25+ none.
    price = inp.economics.sell_price
    price_race = 1 - clamp((price - 12.0) / 13.0, 0, 1)
    return clamp(1.0 - (0.6 * commodity + 0.4 * price_race), 0, 1)


def competition_timing(inp: ScoringInputs) -> tuple[float, dict[str, float]]:
    sat = inp.trigger.saturation
    sat_inv = 1 - clamp(sat.index / 100, 0, 1)
    window = clamp(inp.trigger.window_days / 30, 0, 1)  # 30+ days runway → full
    cat_mom = inp.category_momentum
    cat = cat_mom if cat_mom is not None else _profile(inp.product.category)[3]
    return _weighted({
        "saturation_inv": (sat_inv, 6),
        "window_freshness": (window, 3),
        "differentiation": (_differentiation(inp), 4),
        "category_momentum": (clamp(cat, 0, 1), 2),
    })


# ── 4. Economics (20): margin 7, break-even ROAS 5, return-risk⁻¹ 6, price band 2 ──
def _price_band(price: float) -> float:
    """TikTok Shop impulse sweet spot. $15–$50 converts on impulse; below ~$10 you
    can't buy the customer profitably, above ~$70 the scroll-buy reflex dies."""
    if 15.0 <= price <= 50.0:
        return 1.0
    if price < 15.0:
        return clamp((price - 5.0) / 10.0, 0, 1)        # $5→0, $15→1
    return clamp(1.0 - (price - 50.0) / 50.0, 0, 1)     # $50→1, $100→0


def economics(inp: ScoringInputs) -> tuple[float, dict[str, float]]:
    e = inp.economics
    if not e.landed_known:
        # No real landed cost on file — refuse to score rather than guess (the spec's
        # hard rule: these numbers gate real money). 0/20 with the reason in the breakdown.
        return 0.0, {"NOT_SCORED_no_landed_cost": 0.0}
    margin = clamp((e.gross_margin - 0.40) / (0.70 - 0.40), 0, 1)  # 40%→0, 70%→full
    # Lower break-even ROAS is more feasible vs category CAC. 1.5→full, 5+→0.
    if e.breakeven_roas == float("inf"):
        feasibility = 0.0
    else:
        feasibility = clamp((5.0 - e.breakeven_roas) / (5.0 - 1.5), 0, 1)
    rr = e.return_rate if e.return_rate is not None else 0.05  # assume moderate if unknown
    return_inv = 1 - clamp(rr / 0.10, 0, 1)
    return _weighted({
        "gross_margin": (margin, 7),
        "breakeven_roas": (feasibility, 5),
        "return_risk_inv": (return_inv, 6),
        "impulse_price_band": (_price_band(e.sell_price), 2),
    })


# ── 5. Content Potential (15): angles 6, UGC fit 4, AI-video suitability 5 ──
def content_potential(inp: ScoringInputs) -> tuple[float, dict[str, float]]:
    cons, ugc, ai, *_ = _profile(inp.product.category)
    n_angles = inp.content.distinct_angles
    angles = clamp((n_angles or 4) / 6, 0, 1)  # 6+ distinct angles → full
    return _weighted({
        "distinct_angles": (angles, 6),
        "ugc_fit": (clamp(ugc, 0, 1), 4),
        "ai_video_suitability": (clamp(ai, 0, 1), 5),
    })


# ── 6. Brand Potential (10): repeat/consumable 4, line extension 3, identity 3 ──
def brand_potential(inp: ScoringInputs) -> tuple[float, dict[str, float]]:
    cons, ugc, ai, cat_mom, line, identity = _profile(inp.product.category)
    return _weighted({
        "repeat_consumable": (clamp(cons, 0, 1), 4),
        "line_extension": (clamp(line, 0, 1), 3),
        "identity_community": (clamp(identity, 0, 1), 3),
    })


SUBSCORES = {
    "viral_demo": viral_demo,
    "market_demand": market_demand,
    "competition_timing": competition_timing,
    "economics": economics,
    "content_potential": content_potential,
    "brand_potential": brand_potential,
}
