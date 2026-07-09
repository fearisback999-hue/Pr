"""Road to $1M milestone math — the numbers must be honest and internally consistent."""

import pytest

from tt_engine.roadmap import (
    BLENDED_MARGIN,
    SOURCES,
    plan_million,
    render_roadmap,
)


def test_revenue_target_basic_math():
    p = plan_million(goal_amount=1_000_000, goal_type="revenue", horizon_months=24,
                     aov=45.0, net_margin=0.16)
    assert p.monthly_revenue_needed == pytest.approx(1_000_000 / 24, rel=1e-3)
    assert p.cumulative_revenue_needed == pytest.approx(1_000_000, rel=1e-3)
    # profit is revenue × margin for a revenue target
    assert p.monthly_profit_at_target == pytest.approx(p.monthly_revenue_needed * 0.16, rel=1e-3)
    # orders/day = monthly revenue / aov / 30
    assert p.orders_per_day == pytest.approx(p.monthly_revenue_needed / 45.0 / 30.0, rel=1e-2)


def test_profit_target_needs_far_more_revenue():
    """The whole honesty point: $1M profit needs multiples of $1M in revenue."""
    rev = plan_million(goal_amount=1_000_000, goal_type="revenue", horizon_months=12)
    prof = plan_million(goal_amount=1_000_000, goal_type="profit", horizon_months=12,
                        net_margin=0.16)
    assert prof.cumulative_revenue_needed == pytest.approx(1_000_000 / 0.16, rel=1e-3)
    assert prof.cumulative_revenue_needed > rev.cumulative_revenue_needed * 6
    # profit target should land in the top-percentile reality-check band
    assert "top-1%" in prof.percentile or "top 1%" in prof.percentile


def test_organic_margin_roughly_halves_required_revenue():
    blended = plan_million(goal_amount=1_000_000, goal_type="profit", net_margin=0.16)
    organic = plan_million(goal_amount=1_000_000, goal_type="profit", net_margin=0.35)
    assert organic.cumulative_revenue_needed < blended.cumulative_revenue_needed
    # 0.35 vs 0.16 ≈ 46% of the revenue
    assert organic.cumulative_revenue_needed == pytest.approx(
        blended.cumulative_revenue_needed * (0.16 / 0.35), rel=1e-2)


def test_winners_needed_scales_with_revenue():
    small = plan_million(goal_amount=500_000, goal_type="revenue", horizon_months=36)
    big = plan_million(goal_amount=1_000_000, goal_type="profit", horizon_months=12)
    assert small.winners_needed >= 1
    assert big.winners_needed > small.winners_needed


def test_pod_listings_reduce_the_tiktok_burden():
    without = plan_million(goal_amount=1_000_000, goal_type="revenue", horizon_months=24,
                           pod_listings=0)
    withpod = plan_million(goal_amount=1_000_000, goal_type="revenue", horizon_months=24,
                           pod_listings=200)
    # Same monthly target, but POD carries part of it → fewer TikTok orders/day.
    assert withpod.orders_per_day < without.orders_per_day
    assert any("Etsy POD" in n for n in withpod.notes)


def test_milestone_ladder_flags_the_goal_once():
    p = plan_million(goal_amount=1_000_000, goal_type="revenue", horizon_months=24)
    flagged = [m for m in p.milestones if m.is_goal]
    assert len(flagged) == 1
    # milestones are sorted ascending by monthly revenue
    revs = [m.monthly_revenue for m in p.milestones]
    assert revs == sorted(revs)


def test_percentile_bands():
    assert "below the median" in plan_million(goal_amount=12_000, goal_type="revenue",
                                              horizon_months=24).percentile  # $500/mo
    top = plan_million(goal_amount=1_000_000, goal_type="profit", horizon_months=6).percentile
    assert "top-1%" in top or "top 1%" in top


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError, match="goal_type"):
        plan_million(goal_type="nonsense")
    with pytest.raises(ValueError, match="must be > 0"):
        plan_million(goal_amount=0)
    with pytest.raises(ValueError, match="aov"):
        plan_million(aov=0)
    with pytest.raises(ValueError, match="net_margin"):
        plan_million(net_margin=1.5)


def test_render_roadmap_is_honest_and_sourced():
    text = render_roadmap(plan_million())
    assert "the honest math" in text.lower()
    assert "MILESTONE LADDER" in text
    assert "odds" in text.lower()
    assert "low-probability upside" in text  # the thesis framing carried through
    for url in SOURCES:
        assert url in text


def test_default_is_one_million_revenue():
    p = plan_million()
    assert p.goal_amount == 1_000_000.0
    assert p.goal_type == "revenue"
    assert p.net_margin == BLENDED_MARGIN
