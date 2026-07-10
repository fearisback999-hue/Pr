"""Lifecycle stages, confidence scoring, market analysis, the creative pack, and the
landing-page generator — the 'advanced engine' layer. Every output must show its work."""

from datetime import date, timedelta

import pytest

from tt_engine import pipeline, seed
from tt_engine.analysis import analyze_market
from tt_engine.creative import build_pack
from tt_engine.creative.concepts import cta_variations, hashtags, storyboard
from tt_engine.db import Database, models
from tt_engine.detection import STAGES, classify_lifecycle, evaluate
from tt_engine.economics import compute_economics, unknown_economics
from tt_engine.psychology import analyze
from tt_engine.reports.landing import build_landing_page
from tt_engine.scoring import compute_confidence


def _db(tmp_path):
    return Database(str(tmp_path / "adv.db"))


def _series(units_list, sellers=5, promos=8, ads=4, ad_age=6.0, price=24.99):
    today = date.today()
    n = len(units_list)
    return [models.DailyMetric(
        product_id="T", date=(today - timedelta(days=n - 1 - i)).isoformat(),
        units=int(u), gmv=u * price, price=price, sellers=sellers,
        promo_videos=promos, ads=ads, avg_ad_age=ad_age) for i, u in enumerate(units_list)]


def _ramp(n=35, base=40.0, g=0.10):
    return [base * (1 + g) ** i for i in range(n)]


# ── lifecycle ───────────────────────────────────────────────────────────────────
def test_lifecycle_stages_cover_the_full_arc():
    # brand_new: not enough history
    m = _series(_ramp(8))
    assert classify_lifecycle(m, evaluate(m)).stage == "brand_new"

    # early_trend: accelerating, competition scarce
    m = _series(_ramp(35))
    r = classify_lifecycle(m, evaluate(m))
    assert r.stage == "early_trend"
    assert any("runway" in x for x in r.reasons)   # reasons cite the window

    # growing: accelerating but competition arriving (medium saturation)
    m = _series(_ramp(35), sellers=25, promos=45, ads=18, ad_age=8)
    assert classify_lifecycle(m, evaluate(m)).stage == "growing"

    # peaking: flat sales, entrants still arriving
    flat = [300.0] * 35
    m = _series(flat, sellers=30, promos=60, ads=25, ad_age=20)
    assert classify_lifecycle(m, evaluate(m)).stage == "peaking"

    # oversaturated: the commodity zone, regardless of growth
    m = _series(_ramp(35), sellers=120, promos=300, ads=80, ad_age=35)
    assert classify_lifecycle(m, evaluate(m)).stage == "oversaturated"

    # dead: demand rolling over
    decline = [300 * (0.94 ** i) for i in range(35)]
    m = _series(decline, sellers=40, promos=90, ads=30, ad_age=45)
    assert classify_lifecycle(m, evaluate(m)).stage == "dead"


def test_lifecycle_actionable_flag():
    m = _series(_ramp(35))
    assert classify_lifecycle(m, evaluate(m)).actionable          # early_trend
    m = _series([300.0] * 35, sellers=30, promos=60, ads=25, ad_age=20)
    assert not classify_lifecycle(m, evaluate(m)).actionable      # peaking


def test_lifecycle_stage_names_are_the_declared_set():
    assert set(STAGES) == {"brand_new", "early_trend", "growing", "peaking",
                           "oversaturated", "dead"}


# ── confidence ──────────────────────────────────────────────────────────────────
def test_confidence_clean_data_scores_high():
    m = _series(_ramp(35))
    econ = compute_economics(24.99, 5.0, 1.0, return_rate=0.04)
    c = compute_confidence(m, evaluate(m), econ, ["r1", "r2", "r3"], cross_confirmed=True)
    assert c.score >= 0.95
    assert c.band == "high"
    assert c.reasons == []


def test_confidence_states_every_gap():
    m = _series(_ramp(10))                       # short history
    econ = unknown_economics(24.99)              # no landed cost
    c = compute_confidence(m, evaluate(m), econ, [], cross_confirmed=False)
    assert c.band == "low"
    joined = " ".join(c.reasons)
    assert "day(s) of metrics" in joined
    assert "landed cost" in joined
    assert "review(s)" in joined
    assert "single data source" in joined


def test_confidence_never_silently_zero():
    m = _series(_ramp(7))
    econ = unknown_economics(9.99)
    c = compute_confidence(m, evaluate(m), econ, [])
    assert 0.0 < c.score < 0.5
    assert len(c.reasons) >= 3


# ── market analysis ─────────────────────────────────────────────────────────────
def test_market_analysis_is_data_grounded(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        sr = pipeline.score_stored(db, "P-SOURDOUGHLAME")
        psych = analyze(sr.record.product.name, sr.record.product.reviews, "hobby")
        a = analyze_market(sr, psych)
        text = a.render()
        # Every section present
        for section in ("## SWOT", "## Risk analysis", "## Target audience",
                        "## Objections", "## Marketing angles", "## Offer & pricing",
                        "## Expected lifespan"):
            assert section in text
        # Claims cite computed numbers, not vibes
        assert "margin" in text and "%" in text
        assert "runway" in text
        assert "entrant" in text
        # The offer math is recomputed economics, not asserted
        assert "profit/order" in text
        # Honesty about the psychology source
        assert psych.source in text


def test_market_analysis_without_landed_cost_refuses_offer_math(tmp_path):
    with _db(tmp_path) as db:
        pipeline.daily(db)   # no suppliers
        sr = pipeline.score_stored(db, "P-SOURDOUGHLAME")
        psych = analyze("x", [], "hobby")
        a = analyze_market(sr, psych)
        assert any("no real landed cost" in m for m in a.offer_moves)


# ── creative pack ───────────────────────────────────────────────────────────────
def test_creative_pack_hits_the_volumes_offline():
    product = models.Product(id="P", name="Sourdough Scoring Lame", category="hobby")
    psych = analyze(product.name, ["obsessed, the ear is insane!"], "hobby")
    pack = build_pack(product, psych)
    assert len(pack.hooks) == 50
    assert len({h.text for h in pack.hooks}) == 50          # 50 DISTINCT hooks
    assert len(pack.concepts) == 50
    assert len({c.text for c in pack.concepts}) == 50
    assert len(pack.paid_scripts) == 20
    assert len(pack.organic_scripts) == 20
    assert len(pack.ctas) == 20
    assert len(pack.caption_list) == 20
    assert pack.tag_list and all(t.startswith("#") for t in pack.tag_list)
    assert pack.voiceover and pack.broll and pack.thumbnails
    # organic scripts use soft CTAs, not cart-hammering
    assert all("cart" not in s.cta.lower() for s in pack.organic_scripts)
    # everything swept; templated copy carries no risky claims
    assert not pack.flagged
    text = pack.render()
    assert "Hooks (50)" in text and "UGC concepts (50)" in text
    assert "AI-generated" in text                            # disclosure present


def test_storyboard_and_helpers():
    product = models.Product(id="P", name="Dog Calming Vest", category="pet")
    psych = analyze(product.name, ["my rescue finally slept, obsessed"], "pet")
    pack = build_pack(product, psych, n_hooks=8, n_concepts=8, n_scripts=2)
    scenes = storyboard(pack.paid_scripts[0])
    assert len(scenes) == 5
    assert scenes[0].startswith("SCENE 1")
    assert len(cta_variations(20)) == 20
    tags = hashtags(product)
    assert "#tiktokshop" in tags and len(tags) <= 12


# ── landing page ────────────────────────────────────────────────────────────────
def test_landing_page_is_honest_and_compliant():
    product = models.Product(id="P", name="Cowhide Guitar Strap", category="accessories")
    psych = analyze(product.name, ["gorgeous, no two are the same"], "accessories")
    econ = compute_economics(39.99, 9.0, 2.0, return_rate=0.05)
    page = build_landing_page(product, psych, econ)
    text = page.render()
    assert len(page.headlines) == 5
    assert "## FAQ" in text and "## Comparison table" in text
    # The honesty rules are enforced in the copy itself:
    assert "never fabricate" in text.lower()          # social proof slots, not fake reviews
    assert "anti-pattern" in text                     # fake scarcity called out
    assert "[YOUR POLICY HERE]" in text               # guarantee is yours, not invented
    assert len(page.seo_title) <= 60
    assert len(page.seo_description) <= 155
    assert not page.flagged                            # template copy passes compliance


def test_landing_page_ship_line_reflects_real_warehouse():
    product = models.Product(id="P", name="X", category="home")
    psych = analyze("X", [], "home")
    econ = compute_economics(20.0, 5.0, 1.0)
    us = build_landing_page(product, psych, econ, us_warehouse=True).render()
    intl = build_landing_page(product, psych, econ, us_warehouse=False).render()
    assert "US warehouse" in us
    assert "US warehouse" not in intl
