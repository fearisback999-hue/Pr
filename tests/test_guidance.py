"""Product options, organic marketing, and the authenticity guide — the honest,
researched guidance layer. Invariants: options are framed as validate-not-guaranteed;
organic states the real algorithm signals; authenticity states the real ~30% keep
rate; the discard reality flows into the clothing economics; all three surface in the
dashboard + assistant."""

from tt_engine import organic_marketing, product_ideas
from tt_engine.creative.realism import (
    GENERATIONS_PER_USABLE,
    USABLE_CLIP_RATE,
    render_authenticity_guide,
)


# ── product options ─────────────────────────────────────────────────────────────
def test_ideas_are_a_spread_not_one_product():
    assert len(product_ideas.IDEAS) >= 8
    cats = {i.category for i in product_ideas.IDEAS}
    assert len(cats) >= 5                               # genuinely diverse directions


def test_ideas_are_framed_as_validate_not_guaranteed():
    text = product_ideas.render()
    assert "not guaranteed winners" in text.lower()
    assert "validate" in text.lower()
    # The validation gate is spelled out with real thresholds.
    assert "< 50" in text and "500 reviews" in text
    assert "25" in text and "40%" in text              # the margin band
    assert "import-csv" in text                        # points back at real data


def test_every_idea_states_ai_fit_and_a_watch_out():
    for idea in product_ideas.IDEAS:
        assert idea.why_fits and idea.demo and idea.watch_out
        assert idea.ai_creator                          # honest fit stated
    # Outcome categories keep the real-footage honesty.
    pet = next(i for i in product_ideas.IDEAS if i.category == "pet")
    assert "real" in pet.ai_creator.lower()


def test_ideas_avoid_pure_commodity_framing():
    text = product_ideas.render().lower()
    assert "commodity" in text                          # names the thing to avoid
    assert "defensible" in text


# ── organic marketing ───────────────────────────────────────────────────────────
def test_organic_states_the_real_algorithm_signals():
    text = organic_marketing.render()
    assert "70%" in text or "completion" in text.lower()
    assert "3s" in text or "first 3" in text.lower()    # the hook window
    assert "search" in text.lower()                     # TikTok SEO
    assert "Part 1" in text                             # series play
    names = {s.name for s in organic_marketing.ALGO_SIGNALS}
    assert {"Completion rate", "Watch time", "Shares", "Comments"} <= names


def test_organic_is_honest_about_the_timeline_and_no_hacks():
    text = organic_marketing.render()
    assert "8" in text and "week" in text.lower()       # 8+ weeks before traction
    assert "no bot" in text.lower() or "no hack" in text.lower()
    assert organic_marketing.SOURCES                     # researched, cited


# ── authenticity ────────────────────────────────────────────────────────────────
def test_authenticity_states_the_honest_keep_rate():
    assert USABLE_CLIP_RATE < 0.5
    text = render_authenticity_guide()
    assert f"{int(USABLE_CLIP_RATE*100)}%" in text
    assert f"{GENERATIONS_PER_USABLE}" in text
    assert "discard" in text.lower()
    # It refuses to over-promise.
    assert "identical to a real person" in text
    assert "no one-render magic" in text or "no one render" in text.lower()


def test_authenticity_reuses_the_qa_checklist():
    from tt_engine.creative.realism import ARTIFACT_CHECKLIST
    text = render_authenticity_guide()
    assert any(item in text for item in ARTIFACT_CHECKLIST)
    assert "ON A PHONE" in text
    assert "REAL footage" in text                        # outcome proof stays real


def test_clothing_economics_reflect_the_discard_rate():
    from tt_engine.creative import build_fit_check, build_pack, load_persona
    from tt_engine.db import models
    from tt_engine.economics import compute_economics
    from tt_engine.psychology import analyze
    product = models.Product(id="P-J", name="Wide-Leg Jeans", category="clothing")
    pack = build_pack(product, analyze(product.name, ["fits great"], "apparel"),
                      n_hooks=8, n_concepts=8, n_scripts=3)
    rb = build_fit_check(product, pack.hooks,
                         economics=compute_economics(44.99, 11.0, 3.0), n_clips=1)
    text = rb.render()
    assert "usable" in text.lower()
    assert "Generated ≠ postable" in text or "generated" in text.lower()


# ── assistant routing ───────────────────────────────────────────────────────────
def test_assistant_routes_the_three_topics(tmp_path):
    from tt_engine import pipeline, seed
    from tt_engine.assistant import answer
    from tt_engine.db import Database
    with Database(str(tmp_path / "a.db")) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        assert "ideas" in answer(db, "what could I sell").text.lower() \
            or "options" in answer(db, "what could I sell").text.lower()
        assert "completion" in answer(db, "how do I get free views").text.lower()
        assert "discard" in answer(db, "how do I make it look real").text.lower() \
            or "30%" in answer(db, "how do I make it look real").text
