"""Selection layer: ceiling (can it carry a big month?) + EV (expected dollars per
test) + the $100k operating model. The invariants under test: heuristics are stated,
refusals are absolute (gates / threshold / unpriced), and money math uses the TRUE
fee stack — never the scorer's 6% comparability view."""

from datetime import date, timedelta

import pytest

from tt_engine import pipeline, seed
from tt_engine.db import Database, models
from tt_engine.detection import LifecycleResult, evaluate
from tt_engine.economics import compute_economics, unknown_economics
from tt_engine.roadmap import plan_scale
from tt_engine.scoring import ConfidenceResult
from tt_engine.scoring.algorithm import ScoreBreakdown
from tt_engine.scoring.gates import GateResult
from tt_engine.selection import (
    WINNER_CEILING_MO,
    estimate_ceiling,
    expected_value,
    p_win,
    rank_for_test,
)
from tt_engine.selection.ceiling import _capture_share


# ── fixtures ────────────────────────────────────────────────────────────────────
def _metrics(units_by_day, price=29.99, sellers=8, promos=10, ads=5):
    start = date(2026, 6, 1)
    return [
        models.DailyMetric(
            product_id="P-X", date=(start + timedelta(days=i)).isoformat(),
            units=u, gmv=u * price, price=price, sellers=sellers,
            promo_videos=promos, ads=ads, avg_ad_age=6.0,
        )
        for i, u in enumerate(units_by_day)
    ]


def _breakdown(total, gates_passed=True, failures=()):
    score = models.Score(
        product_id="P-X", date="2026-07-19", viral_demo=0, market_demand=0,
        competition_timing=0, economics=0, content_potential=0, brand_potential=0,
        total=total, gates_passed=gates_passed, gate_failures=list(failures),
        window_days=20.0,
    )
    return ScoreBreakdown(score=score, gate=GateResult(gates_passed, list(failures)))


def _econ(price=29.99, cost=6.0, ship=2.0):
    return compute_economics(price, cost, ship)


GOOD_ECON = _econ()
CONF = ConfidenceResult(score=0.8)
EARLY = LifecycleResult(stage="early_trend")
PEAK = LifecycleResult(stage="peaking")


# ── ceiling ─────────────────────────────────────────────────────────────────────
def test_capture_share_falls_with_saturation():
    assert _capture_share(0) == 0.25
    assert _capture_share(100) == 0.05
    assert _capture_share(30) > _capture_share(70)


def test_ceiling_headroom_favors_early_over_peaking():
    m = _metrics([25] * 21)
    trig = evaluate(m)
    early = estimate_ceiling(m, trig, EARLY, GOOD_ECON)
    peak = estimate_ceiling(m, trig, PEAK, GOOD_ECON)
    assert early.ceiling_monthly > peak.ceiling_monthly
    assert early.market_monthly == peak.market_monthly  # same observed market


def test_ceiling_despikes_the_viral_day():
    """One viral day is content signal, not market size — the market estimate must
    barely move when a 25×-median day lands in the window."""
    base = _metrics([20] * 21)
    spiked = _metrics([20] * 20 + [500])
    trig_b, trig_s = evaluate(base), evaluate(spiked)
    est_b = estimate_ceiling(base, trig_b, EARLY, GOOD_ECON)
    est_s = estimate_ceiling(spiked, trig_s, EARLY, GOOD_ECON)
    # Raw mean would inflate the market ~2.7×; despiked stays under 1.2×.
    assert est_s.market_monthly < est_b.market_monthly * 1.2


def test_ceiling_is_capped_at_the_winner_ceiling():
    m = _metrics([4000] * 21, price=40.0)
    est = estimate_ceiling(m, evaluate(m), EARLY, _econ(40.0, 8.0, 2.0))
    assert est.ceiling_monthly == WINNER_CEILING_MO


def test_ceiling_refuses_contribution_without_landed_cost():
    m = _metrics([25] * 21)
    est = estimate_ceiling(m, evaluate(m), EARLY, unknown_economics(29.99))
    assert est.contribution_monthly is None
    assert est.true_margin is None
    assert any("landed" in n for n in est.notes)
    # Capacity is still estimated — only the money claim is withheld.
    assert est.ceiling_monthly > 0


def test_ceiling_contribution_uses_true_stack_not_6pct():
    m = _metrics([25] * 21)
    est = estimate_ceiling(m, evaluate(m), EARLY, GOOD_ECON)
    # 6%-only margin would give a larger contribution; true stack adds ~3% payment
    # + 15% affiliate, so the true margin must be well below the scorer's view.
    assert est.true_margin < GOOD_ECON.gross_margin
    assert est.contribution_monthly == pytest.approx(
        est.ceiling_monthly * est.true_margin, abs=1.0)


def test_too_small_to_matter_is_flagged():
    m = _metrics([3] * 21, price=9.99)   # tiny market, cheap product
    est = estimate_ceiling(m, evaluate(m), PEAK, _econ(9.99, 2.0, 1.0))
    assert est.too_small_to_matter
    assert any("scale pillar" in n for n in est.notes)
    assert est.products_needed_for_100k > 10


# ── p(win) prior ────────────────────────────────────────────────────────────────
def test_p_win_zero_when_gates_fail():
    assert p_win(_breakdown(90, gates_passed=False, failures=["branded"]),
                 CONF, EARLY) == 0.0


def test_p_win_rises_with_score_edge_and_confidence():
    lo = p_win(_breakdown(80), CONF, EARLY)
    hi = p_win(_breakdown(92), CONF, EARLY)
    assert hi > lo
    shaky = p_win(_breakdown(92), ConfidenceResult(score=0.3), EARLY)
    assert shaky < hi


def test_p_win_penalizes_peaking_and_clamps_at_half():
    early = p_win(_breakdown(88), CONF, EARLY)
    peak = p_win(_breakdown(88), CONF, PEAK)
    assert peak < early
    # No score/confidence combo may ever promise better than a coin flip.
    sky = p_win(_breakdown(100), ConfidenceResult(score=1.0), EARLY)
    assert sky <= 0.50


# ── expected value ──────────────────────────────────────────────────────────────
def _good_ceiling():
    m = _metrics([25] * 21)
    return estimate_ceiling(m, evaluate(m), EARLY, GOOD_ECON)


def test_ev_formula_is_exactly_p_payoff_minus_loss():
    bd, ceiling = _breakdown(85), _good_ceiling()
    ev = expected_value(bd, CONF, EARLY, ceiling, landed_known=True)
    assert ev.eligible
    p = p_win(bd, CONF, EARLY)
    expected = p * ceiling.contribution_monthly * 1.5 - (1 - p) * 0.6 * 200.0
    assert ev.ev == pytest.approx(expected, abs=0.05)


def test_ev_refuses_gated_below_threshold_and_unpriced():
    ceiling = _good_ceiling()
    gated = expected_value(_breakdown(90, False, ["restricted TikTok category"]),
                           CONF, EARLY, ceiling, landed_known=True)
    assert not gated.eligible and "gate" in gated.reason

    low = expected_value(_breakdown(72), CONF, EARLY, ceiling, landed_known=True)
    assert not low.eligible and "TEST verdict" in low.reason

    m = _metrics([25] * 21)
    unpriced_ceiling = estimate_ceiling(m, evaluate(m), EARLY, unknown_economics(29.99))
    unpriced = expected_value(_breakdown(85), CONF, EARLY, unpriced_ceiling,
                              landed_known=False)
    assert not unpriced.eligible and "unpriced" in unpriced.reason
    assert unpriced.ev is None


# ── ranking + pipeline integration ──────────────────────────────────────────────
def test_daily_test_queue_is_ev_ordered_and_gates_stay_absolute(tmp_path):
    with Database(str(tmp_path / "sel.db")) as db:
        seed.seed_sample(db)
        result = pipeline.daily(db)
        assert result.new_candidates                     # something is fundable
        evs = [sr.selection.ev for sr in result.new_candidates]
        assert all(e.eligible for e in evs)              # queue holds eligibles only
        assert [e.ev for e in evs] == sorted((e.ev for e in evs), reverse=True)
        # Every scored record carries selection math; gated products never get an EV.
        for sr in result.scored:
            assert sr.selection is not None
            if not sr.breakdown.score.gates_passed:
                assert not sr.selection.ev.eligible


def test_rank_for_test_puts_eligible_first_then_biggest_blocked(tmp_path):
    with Database(str(tmp_path / "sel2.db")) as db:
        seed.seed_sample(db)
        products = db.all_products()
        scored = [sr for sr in (pipeline.score_stored(db, p.id) for p in products) if sr]
        ranked = rank_for_test(scored)
        flags = [sr.selection.ev.eligible for sr in ranked]
        # All eligibles precede all ineligibles.
        assert flags == sorted(flags, reverse=True)
        blocked = [sr for sr in ranked if not sr.selection.ev.eligible]
        ceilings = [sr.selection.ceiling.ceiling_monthly for sr in blocked]
        assert ceilings == sorted(ceilings, reverse=True)


# ── the $100k operating model ───────────────────────────────────────────────────
def test_plan_scale_defaults_itemize_the_100k_month():
    sp = plan_scale()
    assert sp.monthly_revenue == 100_000.0
    assert sp.winners_needed == 3                        # ceil(100k / 40k ceiling)
    assert sp.monthly_profit == pytest.approx(16_000.0)
    assert sp.working_capital == pytest.approx(
        sp.monthly_ad_budget + sp.cogs_float + sp.contingency)
    assert sp.contingency == pytest.approx(
        0.15 * (sp.monthly_ad_budget + sp.cogs_float))
    # COGS float: 35% of revenue held across a ~14-day payout lag.
    assert sp.cogs_float == pytest.approx(100_000 * 0.35 * (14 / 30), abs=1.0)
    text = sp.render()
    assert "WORKING CAPITAL" in text
    assert "month-N machine, not month one" in text      # sequencing honesty stays


def test_plan_scale_validates_inputs():
    with pytest.raises(ValueError):
        plan_scale(monthly_revenue=0)
    with pytest.raises(ValueError):
        plan_scale(net_margin=1.5)
    with pytest.raises(ValueError):
        plan_scale(cogs_share=0.0)
