"""AI-creator advertising: fit scoring (what a labeled persona may honestly sell),
its tilt on the EV queue, and the per-product plan. The invariant under test: the
persona optimizes delivery, never proof — outcome evidence must be real, and the
module says so everywhere it renders."""

import pytest

from tt_engine import pipeline, seed
from tt_engine.creative import ai_fit, build_creator_plan
from tt_engine.creative.ai_creator import DEFAULT_AFFILIATE_RATE
from tt_engine.db import Database, models
from tt_engine.economics import compute_economics, unknown_economics


def _p(pid="P-X", category="accessories", reviews=()):
    return models.Product(id=pid, name="Thing", category=category,
                          reviews=list(reviews))


# ── fit ─────────────────────────────────────────────────────────────────────────
def test_fit_priors_rank_handling_over_outcome_categories():
    strap = ai_fit(_p(category="accessories"))
    vest = ai_fit(_p(category="pet"))
    serum = ai_fit(_p(category="beauty"))
    assert strap.score > vest.score > serum.score
    assert strap.band == "strong"
    assert serum.band == "poor"


def test_outcome_reviews_lower_fit_and_state_the_evidence_rule():
    reviews = ["my dog finally calmed down during storms",
               "before and after is night and day",
               "results in two weeks, transformation is real"]
    fit = ai_fit(_p(category="home", reviews=reviews))
    clean = ai_fit(_p(category="home"))
    assert fit.score < clean.score
    assert any("OUTCOMES" in r for r in fit.reasons)
    assert any("fabricated evidence" in n for n in fit.never_for)


def test_tactile_reviews_raise_fit():
    reviews = ["easy to install and looks great", "quality feels amazing, well-made",
               "fits perfectly on my strat"]
    fit = ai_fit(_p(category="apparel", reviews=reviews))
    assert fit.score > ai_fit(_p(category="apparel")).score
    assert any("in-hand demo" in r for r in fit.reasons)


def test_fit_always_bans_fabricated_testimonials():
    """Even a perfect-fit product never gets testimonial/before-after clearance."""
    fit = ai_fit(_p(category="accessories"))
    joined = " ".join(fit.never_for)
    assert "fabricated customer testimonials" in joined
    assert "before/after" in joined


# ── the plan ────────────────────────────────────────────────────────────────────
def test_plan_renders_spark_loop_cadence_and_disclosure():
    econ = compute_economics(39.99, 9.0, 3.0)
    plan = build_creator_plan(_p(), econ)
    text = plan.render()
    assert "Spark-boost" in text
    assert "$200 test budget" in text
    assert "48h" in text and "KILL" in text
    assert "posts/day" in text
    assert "AIGC label" in text and "export refuses" in text
    assert "NEVER: fabricated customer testimonials" in text


def test_plan_lane_economics_price_the_affiliate_cut():
    econ = compute_economics(39.99, 9.0, 3.0)
    plan = build_creator_plan(_p(), econ)
    lanes = {ln.label: ln for ln in plan.lanes}
    organic = lanes["persona organic (Spark-assisted)"]
    affiliate = lanes[f"affiliate UGC ({DEFAULT_AFFILIATE_RATE:.0%})"]
    # The persona keeps exactly the affiliate commission per order.
    assert organic.profit_per_order - affiliate.profit_per_order == pytest.approx(
        39.99 * DEFAULT_AFFILIATE_RATE, abs=0.02)
    assert "keeps the" in plan.lane_note
    # And it never pretends organic reach is free.
    assert "earned" in organic.note


def test_plan_refuses_lane_economics_without_landed_cost():
    plan = build_creator_plan(_p(), unknown_economics(29.99))
    assert plan.lanes == []
    assert "landed cost" in plan.lane_note and "fiction" in plan.lane_note


def test_outcome_product_plan_requires_real_affiliate_footage():
    vest = _p(category="pet", reviews=["my dog calmed down instantly"])
    plan = build_creator_plan(vest, compute_economics(34.99, 8.0, 3.0))
    assert any("REQUIRED" in m for m in plan.weekly_mix)


# ── EV integration ──────────────────────────────────────────────────────────────
def test_fit_tilts_p_win_but_is_bounded(tmp_path):
    from tt_engine.detection import LifecycleResult, evaluate
    from tt_engine.scoring import ConfidenceResult
    from tt_engine.selection import estimate_ceiling, expected_value
    from tests.test_selection import _breakdown, _metrics

    m = _metrics([25] * 21)
    econ = compute_economics(29.99, 6.0, 2.0)
    ceiling = estimate_ceiling(m, evaluate(m), LifecycleResult(stage="early_trend"), econ)
    conf, early = ConfidenceResult(score=0.8), LifecycleResult(stage="early_trend")

    base = expected_value(_breakdown(85), conf, early, ceiling, landed_known=True)
    fit_hi = expected_value(_breakdown(85), conf, early, ceiling, landed_known=True,
                            distribution_fit=1.0)
    fit_lo = expected_value(_breakdown(85), conf, early, ceiling, landed_known=True,
                            distribution_fit=0.0)
    assert fit_hi.ev == base.ev                       # perfect fit changes nothing
    assert fit_lo.ev < base.ev                        # poor fit costs EV…
    assert fit_lo.p_win >= base.p_win * 0.70 - 1e-9   # …but never more than ×0.70
    assert "AI-creator fit" in fit_lo.summary


def test_pipeline_scores_carry_fit_and_queue_reflects_it(tmp_path):
    with Database(str(tmp_path / "fit.db")) as db:
        seed.seed_sample(db)
        result = pipeline.daily(db)
        for sr in result.scored:
            assert sr.selection.fit is not None       # every product gets a fit read
        by_id = {sr.breakdown.score.product_id: sr for sr in result.scored}
        # The niche handling products read strong; the beauty commodity reads poor.
        assert by_id["P-COWHIDESTRAP"].selection.fit.band == "strong"
        assert by_id["P-PIMPLEPATCH"].selection.fit.band == "poor"
