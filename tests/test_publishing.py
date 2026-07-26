"""Post from the app — the SANCTIONED, per-post-approved path. Invariants: needs
explicit per-post confirm; only exported + disclosure-carrying assets can post; never
uploads through an unofficial path (honest stub until the official API is wired); the
dashboard post is a deliberate 2-step; manual bookkeeping advances the pipeline."""

import pytest

from tt_engine import publishing
from tt_engine.db import Database, models


@pytest.fixture()
def db(tmp_path):
    with Database(str(tmp_path / "pub.db")) as db:
        db.upsert_product(models.Product(id="P-X", name="Thing", category="home"))
        db.upsert_creative(models.Creative(
            id="C-OK", product_id="P-X", format="UGC", hook="hook", status="exported",
            meta={"aigc_disclosure": "AI-generated content."}))
        db.upsert_creative(models.Creative(
            id="C-BRIEF", product_id="P-X", format="UGC", hook="hook", status="briefed",
            meta={"aigc_disclosure": "AI-generated content."}))
        db.upsert_creative(models.Creative(
            id="C-NODISC", product_id="P-X", format="UGC", hook="hook", status="exported",
            meta={}))
        yield db


# ── per-post permission ─────────────────────────────────────────────────────────
def test_posting_requires_explicit_per_post_confirm(db):
    with pytest.raises(publishing.PostConfirmationRequired):
        publishing.publish_creative(db, "C-OK")            # no confirm
    assert db.get_creative("C-OK").status == "exported"    # not posted


def test_confirmed_but_unwired_is_a_dry_run_never_a_fake_post(db):
    res = publishing.publish_creative(db, "C-OK", confirm=True)
    assert res.dry_run and not res.posted                  # prepared, not uploaded
    assert any("not configured" in n or "official" in n.lower() for n in res.notes)
    # It did NOT lie about posting: status stays exported.
    assert db.get_creative("C-OK").status == "exported"


# ── only exported + disclosed assets ────────────────────────────────────────────
def test_refuses_unexported_asset(db):
    with pytest.raises(ValueError, match="EXPORTED"):
        publishing.publish_creative(db, "C-BRIEF", confirm=True)


def test_refuses_asset_without_disclosure(db):
    with pytest.raises(ValueError, match="disclosure"):
        publishing.publish_creative(db, "C-NODISC", confirm=True)


def test_refuses_unknown_creative(db):
    with pytest.raises(ValueError, match="no creative"):
        publishing.publish_creative(db, "C-GHOST", confirm=True)


# ── official-API-only (never an unofficial path) ────────────────────────────────
def test_configured_but_unwired_raises_clean_not_wired(db, monkeypatch):
    from tt_engine.config import CONFIG
    monkeypatch.setattr(type(CONFIG), "tiktok_posting_available",
                        property(lambda self: True))
    with pytest.raises(publishing.PostingNotWired):
        publishing.publish_creative(db, "C-OK", confirm=True)
    # Still not marked posted — an unwired integration never claims success.
    assert db.get_creative("C-OK").status == "exported"


# ── manual bookkeeping ──────────────────────────────────────────────────────────
def test_mark_posted_advances_only_exported_assets(db):
    publishing.mark_posted(db, "C-OK")
    assert db.get_creative("C-OK").status == "posted"
    with pytest.raises(ValueError):
        publishing.mark_posted(db, "C-BRIEF")              # can't hand-post a plan


# ── the dashboard 2-step ────────────────────────────────────────────────────────
def test_dashboard_post_is_a_deliberate_two_step(tmp_path):
    import http.client
    import threading

    from tt_engine.web import make_server

    db_path = str(tmp_path / "w.db")
    with Database(db_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Thing", category="home"))
        db.upsert_creative(models.Creative(
            id="C-OK", product_id="P-X", format="UGC", hook="h", status="exported",
            meta={"aigc_disclosure": "AI-generated content."}))
    srv = make_server(db_path, host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        def get(path):
            c = http.client.HTTPConnection(*srv.server_address, timeout=10)
            c.request("GET", path)
            r = c.getresponse()
            b = r.read().decode()
            c.close()
            return r.status, b

        # Product page offers a Post link, and states the sanctioned-API stance.
        _, prod = get("/product?id=P-X")
        assert "Post ▶" in prod
        assert "OFFICIAL" in prod and "auto-poster" in prod

        # Step 1: confirmation panel, NOT an immediate post.
        st, step1 = get("/publish?id=C-OK")
        assert st == 200
        assert "Yes, post it" in step1 and "deliberate second step" in step1
        with Database(db_path) as db:
            assert db.get_creative("C-OK").status == "exported"   # nothing posted yet

        # Step 2: confirmed → sanctioned attempt → honest 'not wired' (no fake post).
        st, step2 = get("/publish?id=C-OK&confirm=1")
        assert st == 200
        assert "not configured" in step2 or "official" in step2.lower()
    finally:
        srv.shutdown()
        srv.server_close()
