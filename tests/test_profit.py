"""Profit engineering: portfolio math, the margin lever, and organic screening.

The load-bearing honesty property: this module must never claim per-test
profitability, because that is not a thing that exists.
"""

import math

import pytest

from tt_engine import profit as pf


# ── portfolio probability ─────────────────────────────────────────────────────

def test_p_at_least_one_matches_the_closed_form():
    assert pf.p_at_least_one(0.20, 0) == 0.0
    assert pf.p_at_least_one(0.20, 1) == pytest.approx(0.20)
    assert pf.p_at_least_one(0.20, 3) == pytest.approx(1 - 0.8 ** 3)
    assert pf.p_at_least_one(1.0, 1) == 1.0
    assert pf.p_at_least_one(0.0, 99) == 0.0


def test_p_at_least_one_rises_monotonically_with_shots():
    vals = [pf.p_at_least_one(0.2, n) for n in range(0, 25)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert vals[-1] > 0.99


def test_p_at_least_one_rejects_impossible_inputs():
    for bad in (-0.1, 1.1):
        with pytest.raises(ValueError):
            pf.p_at_least_one(bad, 3)
    with pytest.raises(ValueError):
        pf.p_at_least_one(0.2, -1)


def test_shots_for_confidence_is_the_inverse():
    n = pf.shots_for_confidence(0.20, 0.90)
    assert pf.p_at_least_one(0.20, n) >= 0.90
    assert pf.p_at_least_one(0.20, n - 1) < 0.90


def test_shots_for_confidence_needs_more_shots_for_a_worse_hit_rate():
    assert pf.shots_for_confidence(0.10, 0.9) > pf.shots_for_confidence(0.30, 0.9)


def test_shots_for_confidence_rejects_certainty():
    """You cannot buy 100% — the math diverges, and pretending otherwise is the
    exact false promise this module exists to refuse."""
    for bad in (0.0, 1.0):
        with pytest.raises(ValueError):
            pf.shots_for_confidence(bad, 0.9)
    with pytest.raises(ValueError):
        pf.shots_for_confidence(0.2, 1.0)


# ── the margin lever ──────────────────────────────────────────────────────────

def test_margin_roughly_halves_the_revenue_required():
    blended = pf.plan_profit(400_000, 24, pf.BLENDED_MARGIN)
    organic = pf.plan_profit(400_000, 24, pf.ORGANIC_MARGIN)
    assert blended.monthly_profit == pytest.approx(organic.monthly_profit)
    assert organic.revenue_total < blended.revenue_total / 2
    assert organic.orders_per_day < blended.orders_per_day


def test_plan_profit_is_internally_consistent():
    p = pf.plan_profit(400_000, 24, 0.35)
    assert p.monthly_profit * p.months == pytest.approx(400_000)
    assert p.monthly_revenue * p.margin == pytest.approx(p.monthly_profit)
    assert p.revenue_total == pytest.approx(p.monthly_revenue * p.months)


def test_plan_profit_rejects_nonsense():
    for kwargs in ({"target": 0}, {"months": 0}, {"margin": 0}, {"margin": 1.5}):
        with pytest.raises(ValueError):
            pf.plan_profit(**{"target": 400_000, "months": 24, "margin": 0.35, **kwargs})


# ── organic screening ─────────────────────────────────────────────────────────

def test_screening_beats_cold_testing_on_the_same_budget():
    plan = pf.screening_plan(1180.0, clip_cost=0.40)
    assert plan.candidates_screened > plan.baseline_tests * 5
    assert plan.p_any_winner > plan.baseline_p_any
    assert plan.improvement > 0


def test_screening_degrades_honestly_when_cost_is_unknown():
    """No clip cost means no claim — it must not invent one to look useful."""
    plan = pf.screening_plan(1180.0, clip_cost=None)
    assert plan.candidates_screened == 0
    assert plan.p_any_winner == plan.baseline_p_any     # no unearned improvement
    assert "UNPRICED" in plan.render()


def test_screening_never_exceeds_the_budget():
    for budget in (300.0, 1180.0, 5000.0):
        plan = pf.screening_plan(budget, clip_cost=0.40)
        assert plan.screen_cost + plan.paid_cost <= budget + 1e-6


def test_screening_rejects_a_zero_budget():
    with pytest.raises(ValueError):
        pf.screening_plan(0.0, clip_cost=0.40)


def test_screening_labels_its_assumptions():
    text = pf.screening_plan(1180.0, clip_cost=0.40).render()
    assert "ASSUMPTIONS, not measurements" in text
    assert "superstition" in text        # says plainly how to falsify it


# ── the honest framing ────────────────────────────────────────────────────────

def test_render_refuses_the_always_profitable_premise():
    text = pf.render(clip_cost=0.40)
    assert "is profitable on every test" in text   # "No ... business IS profitable on every test."
    assert "portfolio" in text.lower()
    assert "selling you something" in text


def test_render_states_what_it_does_not_promise():
    text = pf.render(clip_cost=0.40)
    assert "does NOT promise" in text
    assert "most will not" in text
    assert "not a forecast" in text


def test_levers_are_ranked_with_margin_first():
    ls = pf.levers(400_000)
    assert ls[0].name.startswith("1. MARGIN")
    assert len(ls) >= 5
    assert all(l.how for l in ls), "every lever needs an action"


# ── the web surface ───────────────────────────────────────────────────────────

def test_profit_page_shows_both_margins_and_the_caveat(tmp_path):
    from tt_engine.db import Database
    from tt_engine.web.server import page_profit
    with Database(str(tmp_path / "p.db")) as db:
        html = page_profit(db)
    assert "$400,000 profit" in html or "400,000" in html
    assert "profitable on every" in html
    assert "does not promise" in html
    assert "Shots on goal" in html


def test_profit_is_in_the_nav():
    from tt_engine.web.render import _NAV
    assert ("Profit", "/profit") in _NAV
