"""The actor roster + composable video specs. Invariants: the roster loads multiple
actors each with an account; a spec has 3 separately-editable parts and editing one
never disturbs the others; the assembled preview weaves actor+product+prompt;
generation is never triggered by a draft (no credits spent); it all persists + shows
on the dashboard."""

import pytest

from tt_engine.creative import (
    assemble,
    create_spec,
    load_personas,
    persona_by_slug,
    render_spec,
    resolve_actor,
)
from tt_engine.db import Database, models


# ── the roster ──────────────────────────────────────────────────────────────────
def test_roster_loads_multiple_actors_with_accounts():
    roster = load_personas()
    slugs = {p.slug for p in roster}
    assert {"maya", "jordan"} <= slugs                 # at least the two shipped
    for p in roster:
        assert p.account                                # each posts from its own account
    maya = persona_by_slug("maya")
    assert maya and maya.name == "Maya"
    assert persona_by_slug("Jordan").slug == "jordan"   # name lookup works too
    assert persona_by_slug("nobody") is None


def test_actors_are_distinct_people():
    a, b = persona_by_slug("maya"), persona_by_slug("jordan")
    assert a.master_description != b.master_description
    assert a.account != b.account
    assert a.forbidden and b.forbidden                  # each has its own never-change list


# ── the three editable parts ────────────────────────────────────────────────────
@pytest.fixture()
def db(tmp_path):
    with Database(str(tmp_path / "spec.db")) as db:
        db.upsert_product(models.Product(id="P-LAME", name="Sourdough Lame",
                                         category="hobby"))
        db.upsert_product(models.Product(id="P-STRAP", name="Cowhide Strap",
                                         category="accessories"))
        yield db


def test_new_spec_seeds_all_three_parts(db):
    sid = create_spec(db, "P-LAME", actor_slug="jordan")
    spec = db.video_spec(sid)
    assert spec["product_id"] == "P-LAME"
    assert spec["actor_slug"] == "jordan"
    assert spec["prompt"]                               # seeded, editable
    assert spec["status"] == "draft"


def test_editing_the_prompt_leaves_actor_and_product_intact(db):
    sid = create_spec(db, "P-LAME", actor_slug="jordan")
    db.update_video_spec(sid, prompt="Overhead, hands only, no talking")
    spec = db.video_spec(sid)
    assert spec["prompt"] == "Overhead, hands only, no talking"
    assert spec["actor_slug"] == "jordan"              # untouched
    assert spec["product_id"] == "P-LAME"             # untouched


def test_editing_the_actor_leaves_prompt_and_product_intact(db):
    sid = create_spec(db, "P-LAME", actor_slug="jordan", prompt="my exact prompt")
    db.update_video_spec(sid, actor_slug="maya")
    spec = db.video_spec(sid)
    assert spec["actor_slug"] == "maya"
    assert spec["prompt"] == "my exact prompt"         # untouched
    assert spec["product_id"] == "P-LAME"


def test_editing_the_product_leaves_actor_and_prompt_intact(db):
    sid = create_spec(db, "P-LAME", actor_slug="maya", prompt="keep me")
    db.update_video_spec(sid, product_id="P-STRAP")
    spec = db.video_spec(sid)
    assert spec["product_id"] == "P-STRAP"
    assert spec["actor_slug"] == "maya" and spec["prompt"] == "keep me"


def test_assembled_preview_weaves_the_three_parts(db):
    sid = create_spec(db, "P-STRAP", actor_slug="maya", prompt="MY-UNIQUE-PROMPT-TOKEN")
    text = render_spec(db, db.video_spec(sid))
    assert "1. ACTOR" in text and "2. PRODUCT" in text and "3. PROMPT" in text
    assert "Maya" in text                              # actor part
    assert "Cowhide Strap" in text                     # product part
    assert "MY-UNIQUE-PROMPT-TOKEN" in text            # prompt part, verbatim
    assert "Assembled preview" in text
    # And the honest contract: nothing generated, no credits spent.
    assert "no credits spent" in text.lower() or "no credits" in text.lower()


def test_missing_product_or_actor_warns_not_crashes(db):
    sid = create_spec(db, "P-LAME", actor_slug="ghost")   # actor not in roster
    text = render_spec(db, db.video_spec(sid))
    assert "isn't in the roster" in text or "NOT in the roster" in text
    db.update_video_spec(sid, product_id="P-GONE")
    text2 = render_spec(db, db.video_spec(sid))
    assert "PRODUCT not found" in text2                # graceful, no exception


def test_faceless_spec_assembles_without_a_face(db):
    sid = create_spec(db, "P-STRAP", actor_slug="maya", shot_mode="faceless",
                      prompt="hands showing the grain")
    spec = db.video_spec(sid)
    product = db.get_product("P-STRAP")
    text = assemble(product, resolve_actor("maya"), spec["prompt"], "faceless")
    assert "face NOT shown" in text or "FRAMING" in text


def test_create_spec_refuses_unknown_product(db):
    assert create_spec(db, "P-NOPE") is None


# ── it never generates (the credit-safety point) ────────────────────────────────
def test_drafts_do_not_create_creatives(db):
    create_spec(db, "P-LAME", actor_slug="maya")
    create_spec(db, "P-STRAP", actor_slug="jordan")
    assert not db.creatives_for("P-LAME")             # a draft is not a generation
    assert not db.creatives_for("P-STRAP")


# ── dashboard surfaces ──────────────────────────────────────────────────────────
def test_dashboard_shows_roster_and_specs(tmp_path):
    import http.client
    import threading

    from tt_engine import pipeline, seed
    from tt_engine.web import make_server

    db_path = str(tmp_path / "w.db")
    with Database(db_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        create_spec(db, "P-SOURDOUGHLAME", actor_slug="jordan",
                    prompt="ZZ-SPEC-TOKEN")
    srv = make_server(db_path, host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        addr = srv.server_address

        def get(path):
            c = http.client.HTTPConnection(*addr, timeout=10)
            c.request("GET", path)
            b = c.getresponse().read().decode()
            c.close()
            return b

        adv = get("/advertising")
        assert "Actor roster" in adv and "maya" in adv and "jordan" in adv

        prod = get("/product?id=P-SOURDOUGHLAME")
        assert "Video specs" in prod
        assert "ZZ-SPEC-TOKEN" in prod                 # the editable prompt shows
        assert "edit before you generate" in prod.lower() or "before you generate" in prod.lower()
    finally:
        srv.shutdown()
        srv.server_close()
