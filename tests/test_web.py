"""Dashboard smoke tests: spin the real server on an ephemeral port and hit every
route against a seeded DB — the pages must render with live data, not error."""

import http.client
import threading

import pytest

from tt_engine import pipeline, seed
from tt_engine.db import Database
from tt_engine.web import make_server


@pytest.fixture()
def server(tmp_path):
    db_path = str(tmp_path / "web.db")
    with Database(db_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
    srv = make_server(db_path, host="127.0.0.1", port=0)  # ephemeral port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address
    srv.shutdown()
    srv.server_close()


def _get(addr, path):
    conn = http.client.HTTPConnection(*addr, timeout=10)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    return resp.status, body


def test_overview_shows_board_and_next_steps(server):
    status, body = _get(server, "/")
    assert status == 200
    assert "Ranked board" in body and "What to do next" in body
    assert "P-SOURDOUGHLAME" in body
    assert 'class="chip TEST"' in body        # at least one TEST-ready product
    assert 'class="chip KILL"' in body        # and the gated ones show as KILL


def test_product_page_renders_scorecard_and_next_step(server):
    status, body = _get(server, "/product?id=P-SOURDOUGHLAME")
    assert status == 200
    assert "Scorecard" in body and "break-even ROAS" in body
    assert "<b>Next:</b>" in body

    status, _ = _get(server, "/product?id=NOPE")
    assert status == 404


def test_advertising_page_shows_mcp_config_and_tests(server):
    status, body = _get(server, "/advertising")
    assert status == 200
    assert "HIGGSFIELD_API_KEY" in body
    assert "mcp.higgsfield.ai" in body          # the real, verified OAuth-agent endpoint
    assert "Creative batches" in body and "Live ad tests" in body
    assert "never spends money" in body       # the guardrail is stated on the page


def test_budget_page_calculators_respond_to_params(server):
    status, body = _get(server, "/budget?capital=9000&pod_target=2000&pod_profit=10")
    assert status == 200
    assert "capital $9,000" in body           # capital plan recomputed from the form
    assert "target $2,000/mo" in body         # POD plan recomputed from the form
    assert "listing" in body


def test_budget_page_month_one_section(server):
    status, body = _get(server, "/budget?m1_tests=3&m1_budget=250")
    assert status == 200
    assert "Month one" in body
    assert "INITIAL CASH NEEDED" in body
    assert "ad tests (3 × $250)" in body       # recomputed from the form
    assert "EXPECTED VALUE" in body
    assert "negative by design" in body        # the honesty note stays on the page


def test_creators_page_links_marketplaces(server):
    status, body = _get(server, "/creators")
    assert status == 200
    assert "affiliate-us.tiktok.com" in body
    assert "creatormarketplace.tiktok.com" in body
    assert "packet" in body                   # points at the outreach packet command


def test_unknown_route_404s(server):
    status, _ = _get(server, "/nope")
    assert status == 404


def test_million_page_computes_and_stays_honest(server):
    status, body = _get(server, "/million?goal=1000000&type=revenue&months=24")
    assert status == 200
    assert "Road to $1M" in body
    assert "revenue / month needed" in body
    assert "Milestone ladder" in body
    assert "low-probability upside" in body        # the thesis framing is on the page
    assert "fewer than 10% of new sellers survive" in body
    assert "greyjournal.net" in body               # a researched source is linked


def test_million_page_profit_target_shows_top_percentile(server):
    status, body = _get(server, "/million?goal=1000000&type=profit&months=12&margin=0.16")
    assert status == 200
    assert "top-1%" in body or "top 1%" in body


def test_million_page_rejects_bad_margin_gracefully(server):
    status, body = _get(server, "/million?margin=2")
    assert status == 200                            # not a 500
    assert "net_margin" in body


def test_search_page_filters_and_renders(server):
    status, body = _get(server, "/search?q=strap")
    assert status == 200
    assert "P-COWHIDESTRAP" in body
    assert "P-PIMPLEPATCH" not in body              # keyword filter works
    assert "<svg" in body                            # trend sparkline rendered
    assert "will not) scrape" in body                # the no-scraping stance is stated

    status, body = _get(server, "/search?category=beauty")
    assert status == 200
    assert "P-PIMPLEPATCH" in body and "P-COWHIDESTRAP" not in body

    status, body = _get(server, "/search?min_price=30&max_price=45")
    assert "P-COWHIDESTRAP" in body                  # $39.99 in range
    assert "P-SOURDOUGHLAME" not in body             # $21.99 out of range


def test_assistant_page_answers_grounded_in_live_data(server):
    status, body = _get(server, "/assistant")
    assert status == 200
    assert "never invents numbers" in body            # the honesty contract, on-page

    status, body = _get(server, "/assistant?q=is+P-PIMPLEPATCH+worth+testing")
    assert status == 200
    assert "offline routing" in body                  # mode labeled
    assert "P-PIMPLEPATCH" in body
    assert "commodity-saturated" in body              # the real gate, from live data


def test_product_page_shows_lifecycle_confidence_and_chart(server):
    status, body = _get(server, "/product?id=P-SOURDOUGHLAME")
    assert status == 200
    assert "early trend" in body                     # lifecycle chip
    assert "Data confidence" in body
    assert "<svg" in body                            # units sparkline
    assert "Suppliers (best first)" in body          # auto-recommended supplier (★)
    assert "★" in body


def test_overview_shows_autopilot_and_run_proposes(server):
    status, body = _get(server, "/")
    assert status == 200
    assert "Autopilot — automated, approval-gated" in body
    assert "nothing runs until you approve" in body

    status, _ = _get(server, "/autopilot/run")
    assert status == 303                               # propose + redirect, no page spend

    status, body = _get(server, "/")
    assert "approve ▶" in body                         # internal steps approvable here
    assert "clears itself when done" in body           # manual steps labeled


def test_autopilot_web_approve_executes_internal_only(server):
    _get(server, "/autopilot/run")
    _, body = _get(server, "/")
    import re
    ids = re.findall(r"/autopilot/approve\?id=(\d+)", body)
    assert ids                                         # at least one internal pending
    status, _ = _get(server, f"/autopilot/approve?id={ids[0]}")
    assert status == 303
    _, body2 = _get(server, "/")
    assert f"/autopilot/approve?id={ids[0]}" not in body2   # executed, gone from queue

    # Garbage ids are a safe no-op redirect, never a 500.
    status, _ = _get(server, "/autopilot/approve?id=zzz")
    assert status == 303


def test_overview_ranks_the_test_queue_by_ev(server):
    status, body = _get(server, "/")
    assert status == 200
    assert "Test queue — ranked by expected value" in body
    assert "fund in this order" in body                # eligible rows say why they rank
    assert "TRUE fee" in body                          # the money math is the true stack
    assert "48h kill timer" in body                    # EV orders; the timer decides


def test_product_page_shows_selection_math(server):
    status, body = _get(server, "/product?id=P-SOURDOUGHLAME")
    assert status == 200
    assert "Selection math" in body
    assert "ceiling" in body
    assert "p(win)" in body

    # A gated product shows the refusal, not a number.
    status, body = _get(server, "/product?id=P-PIMPLEPATCH")
    assert status == 200
    assert "no EV" in body


def test_advertising_page_states_the_ai_creator_program(server):
    status, body = _get(server, "/advertising")
    assert status == 200
    assert "AI creator program" in body
    assert "fabricated" in body                        # the evidence rule, on-page
    assert "ai-plan" in body                           # the per-product command


def test_product_page_shows_ai_creator_fit(server):
    status, body = _get(server, "/product?id=P-COWHIDESTRAP")
    assert status == 200
    assert "AI-creator fit" in body
    assert "never:" in body                            # the may-never list renders

    # An outcome-proof product carries the fabricated-evidence warning.
    status, body = _get(server, "/product?id=P-DOGCALMVEST")
    assert status == 200
    assert "fabricated evidence" in body


def test_million_page_itemizes_the_100k_month(server):
    status, body = _get(server, "/million")
    assert status == 200
    assert "The $100k month, itemized" in body
    assert "Working capital" in body
    assert "COGS float" in body
    assert "month-N machine, not month one" in body     # sequencing honesty on-page


def test_overview_links_to_playbook(server):
    status, body = _get(server, "/")
    assert status == 200
    assert "/playbook" in body
    assert "playbook steps" in body


def test_playbook_page_renders_all_phases(server):
    status, body = _get(server, "/playbook")
    assert status == 200
    assert "Zero-to-hero playbook" in body
    assert "0 — Business foundation" in body
    assert "12 — Systemize" in body
    # An auto step already satisfied by the seeded+scored DB shows as done.
    assert "Get real market data into the engine" in body


def test_playbook_page_shows_sourced_facts_and_links(server):
    import html as _html

    from tt_engine.playbook import VERIFIED_DATE, all_sources

    status, body = _get(server, "/playbook")
    assert status == 200
    assert f"Sources (verified {VERIFIED_DATE})" in body
    sources = all_sources()
    assert sources  # the research pass grounded real steps
    # URLs render HTML-escaped (query-string & becomes &amp;) — compare escaped forms.
    assert all(f"href='{_html.escape(url)}'" in body for url in sources)
    assert "irs.gov" in body.lower()          # a real primary source made it onto the page
    assert "seller-us.tiktok.com" in body     # TikTok's own Seller Center essays cited


def test_playbook_toggle_persists_and_redirects(server):
    status, _ = _get(server, "/playbook/toggle?id=biz-structure&done=1")
    assert status == 303  # redirect back to /playbook, no money moved

    status, body = _get(server, "/playbook")
    assert status == 200
    # Toggling back off works too.
    _get(server, "/playbook/toggle?id=biz-structure&done=0")
    status, body2 = _get(server, "/playbook")
    assert status == 200
    assert body != body2  # the page actually reflects the state change


def test_playbook_toggle_ignores_auto_steps(server):
    """An auto step's completion is derived from DB state — a toggle link must not
    be able to fake it."""
    status, before = _get(server, "/playbook")
    _get(server, "/playbook/toggle?id=first-test-verdict&done=0")
    status, after = _get(server, "/playbook")
    assert status == 200
    assert before == after  # no-op: auto steps ignore manual toggles
