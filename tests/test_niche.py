"""Niche-vs-commodity: the engine must reward defensible niche products and reject
generic commodities (the pimple-patch trap) — not just score them lower, GATE them."""

from datetime import date, timedelta

from tt_engine import pipeline, seed
from tt_engine.db import Database, models
from tt_engine.detection import evaluate
from tt_engine.economics import compute_economics
from tt_engine.psychology import commodity_signal
from tt_engine.scoring import ScoringInputs, check_gates
from tt_engine.scoring.gates import COMMODITY_SATURATION_MAX
from tt_engine.scoring.subscores import _differentiation, competition_timing


def _db(tmp_path):
    return Database(str(tmp_path / "niche.db"))


def _metrics(sellers, promos, ads, ad_age, price=24.99, n=35):
    """Flat series with a fixed competition level — isolates the saturation gate."""
    today = date.today()
    return [models.DailyMetric(
        product_id="T", date=(today - timedelta(days=n - 1 - i)).isoformat(),
        units=100, gmv=100 * price, price=price, sellers=sellers,
        promo_videos=promos, ads=ads, avg_ad_age=ad_age) for i in range(n)]


def _inputs(category, price, sellers, promos, ads, ad_age, commodity=0.0,
            cost=6.0, ship=1.0):
    product = models.Product(id="T", name="T", category=category)
    trigger = evaluate(_metrics(sellers, promos, ads, ad_age, price))
    econ = compute_economics(price, cost, ship, return_rate=0.04)
    return ScoringInputs(product=product, trigger=trigger, economics=econ,
                        commodity_signal=commodity)


# ── the commodity-saturation hard gate ─────────────────────────────────────────
def test_commodity_saturation_gate_disqualifies_crowded_products():
    """A flooded commodity (many sellers/promos/ads) is gated regardless of anything else
    — this is what rejects the pimple-patch/tumbler trap."""
    crowded = _inputs("beauty", 16.99, sellers=120, promos=300, ads=80, ad_age=35)
    assert crowded.trigger.saturation.index >= COMMODITY_SATURATION_MAX
    gate = check_gates(crowded)
    assert not gate.passed
    assert any("commodity-saturated" in f for f in gate.failures)


def test_low_competition_niche_clears_the_saturation_gate():
    niche = _inputs("hobby", 21.99, sellers=4, promos=4, ads=3, ad_age=6)
    assert niche.trigger.saturation.index < COMMODITY_SATURATION_MAX
    assert check_gates(niche).passed  # healthy margin + low saturation → clear


def test_good_margins_do_not_save_a_commodity():
    """Great economics can't override the saturation gate — the pimple-patch lesson:
    fine margins, but a crowded red ocean you shouldn't enter."""
    fat_margin_commodity = _inputs("beauty", 24.99, sellers=150, promos=400, ads=90,
                                   ad_age=40, cost=3.0, ship=1.0)
    assert fat_margin_commodity.economics.gross_margin > 0.45  # economics are fine
    gate = check_gates(fat_margin_commodity)
    assert not gate.passed
    assert any("commodity-saturated" in f for f in gate.failures)


# ── the differentiation sub-score ──────────────────────────────────────────────
def test_niche_scores_higher_differentiation_than_commodity():
    niche = _inputs("hobby", 29.99, sellers=4, promos=4, ads=3, ad_age=6)      # defensible
    commodity = _inputs("electronics", 8.99, sellers=10, promos=5, ads=4, ad_age=7)  # generic
    assert _differentiation(niche) > 0.75
    assert _differentiation(commodity) < 0.30
    # and it flows into the Competition Timing sub-score
    niche_ct, niche_parts = competition_timing(niche)
    comm_ct, comm_parts = competition_timing(commodity)
    assert niche_parts["differentiation"] > comm_parts["differentiation"]


def test_commodity_review_language_lowers_differentiation():
    """Even at the same (low) current competition, a product whose reviews scream
    'everyone sells this' scores less defensible than a genuine niche find."""
    quiet = _inputs("home", 24.99, sellers=6, promos=6, ads=4, ad_age=7, commodity=0.0)
    flooded_talk = _inputs("home", 24.99, sellers=6, promos=6, ads=4, ad_age=7,
                           commodity=0.9)
    assert _differentiation(quiet) > _differentiation(flooded_talk)


def test_explicit_differentiation_input_overrides_heuristic():
    inp = _inputs("electronics", 8.99, sellers=10, promos=5, ads=4, ad_age=7)
    inp.differentiation = 0.95
    assert _differentiation(inp) == 0.95


def test_commodity_signal_detects_me_too_language():
    assert commodity_signal([]) == 0.0
    assert commodity_signal(["I love this, obsessed"]) == 0.0
    flooded = ["everyone sells this exact one", "saw it on every shop, prices all over",
               "nothing special, race to the bottom"]
    assert commodity_signal(flooded) >= 0.9


# ── end-to-end on the seed feed ────────────────────────────────────────────────
def test_seed_surfaces_niche_and_rejects_commodities(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        result = pipeline.daily(db)
        by_id = {s.record.product.id: s for s in result.scored}

        # The niche finds are the attack-ready winners.
        winners = {c.record.product.id for c in result.new_candidates}
        assert "P-SOURDOUGHLAME" in winners      # hobby niche
        assert "P-COWHIDESTRAP" in winners       # aesthetic accessory niche

        # The generic commodities are all rejected — pimple patches, tumbler, posture
        # corrector on the saturation gate; phone stand / cable on thin margin.
        for pid in ("P-PIMPLEPATCH", "P-TRENDYTUMBLER", "P-POSTURECORR"):
            score = by_id[pid].breakdown.score
            assert not score.gates_passed
            assert any("commodity-saturated" in f for f in score.gate_failures), pid
        assert not by_id["P-PHONESTAND"].breakdown.recommended
        assert not by_id["P-CHEAPCABLE"].breakdown.recommended
