"""Seed expansion — finding products FROM products.

The load-bearing honesty property: expansion produces LEADS. It must never
present a suggestion as a validated product, because it has no demand data
about any of them.
"""

import pytest

from tt_engine.db import Database, models
from tt_engine.expand import AXES, expand, expand_all


def _db(tmp_path, category="fitness", name="Doorway Pull Up Bar"):
    db = Database(str(tmp_path / "e.db"))
    db.upsert_product(models.Product(id="P1", name=name, category=category))
    return db


def test_expansion_covers_every_axis(tmp_path):
    db = _db(tmp_path)
    exp = expand(db, "P1")
    axes_used = {l.axis for l in exp.leads}
    assert axes_used == set(AXES), f"missing axes: {set(AXES) - axes_used}"
    db.close()


def test_leads_are_specific_enough_to_act_on(tmp_path):
    db = _db(tmp_path)
    exp = expand(db, "P1")
    prompts = [l.prompt.lower() for l in exp.leads]
    assert any("grip" in p for p in prompts)
    assert any("wall-mounted" in p for p in prompts)
    for l in exp.leads:
        assert len(l.prompt) > 4
        assert l.why and l.seed_name == "Doorway Pull Up Bar"
    db.close()


def test_why_text_is_written_not_templated(tmp_path):
    """A generic 'needs <axis description>' reads like filler and gets skimmed."""
    db = _db(tmp_path)
    exp = expand(db, "P1")
    whys = {l.why for l in exp.leads}
    assert len(whys) >= 4, "every axis should give a different reason"
    assert not any("needs what it needs" in w for w in whys)
    db.close()


def test_unknown_category_still_produces_usable_leads(tmp_path):
    db = _db(tmp_path, category="something-weird")
    exp = expand(db, "P1")
    assert exp is not None and len(exp.leads) == len(AXES)
    db.close()


def test_expansion_routes_to_the_actor_whose_lane_covers_it(tmp_path):
    db = _db(tmp_path, category="beauty", name="Scalp Massager")
    assert expand(db, "P1").actor == "Maya"
    db.close()


def test_expansion_says_when_no_actor_covers_the_lane(tmp_path):
    db = _db(tmp_path, category="fitness")
    exp = expand(db, "P1")
    assert exp.actor is None
    assert "no actor covers" in exp.render()
    db.close()


def test_render_never_claims_the_leads_are_products(tmp_path):
    db = _db(tmp_path)
    text = expand(db, "P1").render()
    assert "LEADS, not products" in text
    assert "still has to pass the same checks" in text
    # It must not imply demand it doesn't have.
    for banned in ("trending", "viral", "hot right now", "proven winner"):
        assert banned not in text.lower()
    db.close()


def test_unknown_product_returns_none(tmp_path):
    db = _db(tmp_path)
    assert expand(db, "NOPE") is None
    db.close()


def test_expand_all_prefers_the_best_scoring_seeds(tmp_path):
    """A winner is the best seed there is — you already know that audience buys."""
    db = Database(str(tmp_path / "e.db"))
    for i, total in enumerate([40.0, 90.0, 65.0]):
        pid = f"P{i}"
        db.upsert_product(models.Product(id=pid, name=f"Thing {i}", category="home"))
        db.upsert_score(models.Score(
            product_id=pid, date="2026-01-01", viral_demo=1, market_demand=1,
            competition_timing=1, economics=1, content_potential=1,
            brand_potential=1, total=total, gates_passed=True, gate_failures=[],
            window_days=10))
    top = expand_all(db, limit=1)
    assert top[0].seed.id == "P1"      # the 90-scorer
    db.close()


def test_llm_output_is_parsed_and_bad_lines_ignored(tmp_path):
    class _Fake:
        available = True
        def complete_text(self, system, user, max_tokens=4000):
            return ("accessory | Silicone Grip Pads | saves their hands\n"
                    "not-an-axis | Nonsense | should be dropped\n"
                    "garbage line with no pipes\n"
                    "upgrade | Wall-Mounted Rack | the next purchase up")
    db = _db(tmp_path)
    exp = expand(db, "P1", llm=_Fake())
    assert exp.mode == "llm"
    assert len(exp.leads) == 2
    assert exp.leads[0].prompt == "Silicone Grip Pads"
    db.close()


def test_llm_failure_falls_back_to_the_offline_frame(tmp_path):
    from tt_engine.llm import LLMUnavailable
    class _Broken:
        available = True
        def complete_text(self, system, user, max_tokens=4000):
            raise LLMUnavailable("no network")
    db = _db(tmp_path)
    exp = expand(db, "P1", llm=_Broken())
    assert exp.mode == "offline"
    assert exp.leads, "must still give leads when the model is unavailable"
    db.close()


def test_product_page_shows_leads(tmp_path):
    from tt_engine.web.server import page_product
    db = _db(tmp_path, category="beauty", name="Scalp Massager")
    html = page_product(db, "P1")
    assert "More products from this one" in html
    assert "leads, not verified products" in html
    db.close()
