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
    assert "P-SCALPMASSAGER" in body
    assert 'class="chip TEST"' in body        # at least one TEST-ready product
    assert 'class="chip KILL"' in body        # and the gated ones show as KILL


def test_product_page_renders_scorecard_and_next_step(server):
    status, body = _get(server, "/product?id=P-SCALPMASSAGER")
    assert status == 200
    assert "Scorecard" in body and "break-even ROAS" in body
    assert "<b>Next:</b>" in body

    status, _ = _get(server, "/product?id=NOPE")
    assert status == 404


def test_advertising_page_shows_mcp_config_and_tests(server):
    status, body = _get(server, "/advertising")
    assert status == 200
    assert "HIGGSFIELD_MCP_URL" in body
    assert "Creative batches" in body and "Live ad tests" in body
    assert "never spends money" in body       # the guardrail is stated on the page


def test_budget_page_calculators_respond_to_params(server):
    status, body = _get(server, "/budget?capital=9000&pod_target=2000&pod_profit=10")
    assert status == 200
    assert "capital $9,000" in body           # capital plan recomputed from the form
    assert "target $2,000/mo" in body         # POD plan recomputed from the form
    assert "listing" in body


def test_creators_page_links_marketplaces(server):
    status, body = _get(server, "/creators")
    assert status == 200
    assert "affiliate-us.tiktok.com" in body
    assert "creatormarketplace.tiktok.com" in body
    assert "packet" in body                   # points at the outreach packet command


def test_unknown_route_404s(server):
    status, _ = _get(server, "/nope")
    assert status == 404


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
