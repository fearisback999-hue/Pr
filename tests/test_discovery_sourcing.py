"""How-finding-works + scouting + the US/fast sourcing guide. Invariants: the honest
mechanics are stated (no scraping; engine filters candidates YOU bring), the scout
workflow ends in real log commands, the sourcing guide leads with US/fast + the
sample-order discipline, and both route in the assistant + render on the dashboard."""

from tt_engine import discovery
from tt_engine.sourcing.guide import SOURCES as SUPPLIER_SOURCES
from tt_engine.sourcing.guide import render as sourcing_render


# ── how finding works / scouting ────────────────────────────────────────────────
def test_finding_explainer_is_honest_about_no_scraping():
    text = discovery.render()
    low = text.lower()
    assert "does not browse" in low or "doesn't browse" in low
    assert "never scrape" in low or "never scrapes" in low
    assert "filter" in low and "score" in low
    # It states the two candidate routes.
    assert "import-csv" in text                         # data feed
    assert "scout" in low                               # your own scouting


def test_scout_lists_free_sources_and_the_demand_bar():
    text = discovery.render()
    assert "Creative Center" in text                    # TikTok's own free tool
    assert "TikTokMadeMeBuyIt" in text
    assert "Amazon" in text                             # cross-platform check
    # The niche-with-demand criteria are concrete.
    assert "where can I buy" in text                    # a real demand signal
    assert "< 50" in text and "500 reviews" in text     # saturation bar
    assert "45%" in text                                # the margin gate


def test_scout_ends_in_real_log_commands():
    text = discovery.render()
    for cmd in ("add --name", "add-metric", "add-supplier", "scorecard"):
        assert cmd in text
    assert "select" in text                             # then rank the finds


def test_scout_is_honest_it_cant_do_it_for_you():
    low = discovery.render().lower()
    assert "human work" in low
    assert "can't do it for you" in low or "cannot do it for you" in low


# ── the US / fast sourcing guide ────────────────────────────────────────────────
def test_sourcing_guide_leads_with_us_and_fast():
    text = sourcing_render()
    assert "US warehouse" in text
    assert "24" in text and "48h" in text               # the tracking-scan window
    assert "3–6 day" in text or "3-6 day" in text


def test_sourcing_guide_has_real_us_suppliers():
    names = {s.name for s in SUPPLIER_SOURCES}
    assert "CJ Dropshipping" in names
    assert "TopDawg" in names
    assert any("Amazon" in n for n in names)            # MCF for fastest once proven
    assert len(SUPPLIER_SOURCES) >= 5
    for s in SUPPLIER_SOURCES:
        assert s.us_speed and s.good_for and s.watch_out


def test_sourcing_guide_enforces_sample_and_real_cost():
    text = sourcing_render()
    assert "SAMPLE" in text                             # mandatory before scaling
    assert "add-supplier" in text and "--us-warehouse" in text
    assert "landed cost" in text.lower()
    # Honest about what it can't do.
    assert "can't order" in text.lower() or "cannot order" in text.lower()


# ── assistant routing ───────────────────────────────────────────────────────────
def test_assistant_routes_supplier_and_finding_questions(tmp_path):
    from tt_engine import pipeline, seed
    from tt_engine.assistant import answer
    from tt_engine.db import Database
    with Database(str(tmp_path / "a.db")) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        sup = answer(db, "where do I find a US supplier with fast shipping").text.lower()
        assert "us warehouse" in sup or "cj dropshipping" in sup
        assert "sample" in sup
        find = answer(db, "how does finding products actually work").text.lower()
        assert "scrape" in find or "filter" in find


# ── dashboard ───────────────────────────────────────────────────────────────────
def test_ideas_page_shows_finding_and_sourcing(tmp_path):
    import http.client
    import threading

    from tt_engine import pipeline, seed
    from tt_engine.db import Database
    from tt_engine.web import make_server

    db_path = str(tmp_path / "w.db")
    with Database(db_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
    srv = make_server(db_path, host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection(*srv.server_address, timeout=10)
        conn.request("GET", "/ideas")
        body = conn.getresponse().read().decode()
        conn.close()
        assert "How finding works" in body
        assert "Where to source" in body
        assert "CJ Dropshipping" in body
        assert "TikTokMadeMeBuyIt" in body
    finally:
        srv.shutdown()
        srv.server_close()
