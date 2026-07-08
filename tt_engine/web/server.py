"""The local dashboard — everything on one site, served from the SQLite DB on your own
machine. Stdlib http.server only: no framework, no build step, no external assets, so it
runs on an offline desk server with `python -m tt_engine.cli serve`.

Read-only by design: the dashboard SHOWS state and hands you the exact command for every
next action. Anything that spends money (creative --confirm, ad launches) stays a
deliberate CLI step — a browser tab must never be one accidental click away from spend.
"""

from __future__ import annotations

from datetime import date as _date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .. import pipeline
from ..capital import plan_capital, plan_pod
from ..config import CONFIG
from ..db import Database
from ..guide import all_steps, next_step
from ..reports.scorecard import render_scorecard, verdict
from ..validation import KILL_HOURS, hours_below_breakeven, summarize_tests
from .render import chip, esc, kpi, md_to_html, page, table

CREATOR_LINKS = [
    ("TikTok Shop Affiliate Center", "https://affiliate-us.tiktok.com",
     "Open collaboration + targeted invites — the main channel for TikTok Shop affiliates."),
    ("TikTok Creator Marketplace", "https://creatormarketplace.tiktok.com",
     "TikTok's official creator search (audience size, engagement, categories)."),
    ("Insense", "https://insense.pro", "UGC + paid-usage creators, brief-based workflow."),
    ("Billo", "https://billo.app", "Fixed-price UGC videos, fast turnaround."),
    ("Collabstr", "https://collabstr.com", "Marketplace of UGC/influencer creators, pay per deal."),
    ("Twirl", "https://www.twirl.so", "Vetted UGC creators, subscription batches."),
    ("Fiverr — UGC videos", "https://www.fiverr.com/search/gigs?query=ugc%20tiktok%20video",
     "Cheapest tier — good for volume-testing hooks before paying premium creators."),
    ("Upwork — UGC creators", "https://www.upwork.com/services/ugc",
     "Longer-term creator relationships, hourly or per-asset."),
]


def _f(q: dict, key: str, default: float) -> float:
    try:
        return float(q.get(key, [None])[0])
    except (TypeError, ValueError):
        return default


def _i(q: dict, key: str, default: int) -> int:
    return int(_f(q, key, default))


# ── page builders (pure: Database in, HTML out) ─────────────────────────────────
def page_overview(db: Database) -> str:
    scores = db.board()
    body = ["<h1>Overview</h1>"]

    attack = sum(1 for s in scores if s.gates_passed and s.total >= CONFIG.score_threshold)
    live_tests = {t.creative_id.rsplit("-", 1)[0] for p in db.all_products()
                  for t in db.tests_for_product(p.id)}
    body.append("<div class=kpis>"
                + kpi(str(len(scores)), "products scored")
                + kpi(str(attack), "TEST-ready now")
                + kpi(str(len(live_tests)), "products with live tests")
                + kpi(f"{CONFIG.score_threshold:.0f}", "score threshold")
                + "</div>")

    body.append("<h2>What to do next</h2><div class=panel>")
    steps = all_steps(db)
    if not steps:
        body.append("<p class=mut>Nothing in the pipeline yet — import a CSV or add a "
                    "product: <code>python -m tt_engine.cli import-csv …</code></p>")
    for s in steps[:12]:
        cmd = f"<div class=cmd><code>{esc(s.command)}</code></div>" if s.command else ""
        body.append(f"<div class=step><a href='/product?id={esc(s.product_id)}'>"
                    f"<b>{esc(s.product_id)}</b></a> "
                    f"<span class='chip info'>{esc(s.stage)}</span> "
                    f"{esc(s.action)}{cmd}</div>")
    body.append("</div>")

    body.append("<h2>Ranked board</h2><div class=panel>")
    if scores:
        rows = []
        for s in scores:
            p = db.get_product(s.product_id)
            v = verdict(s.gates_passed, s.total)
            rows.append([
                f"<a href='/product?id={esc(s.product_id)}'>{esc(s.product_id)}</a>",
                esc(p.name if p else "—"),
                f"{s.total:.0f}", chip(v),
                f"~{s.window_days:.0f}d" if s.window_days else "—",
                esc(", ".join(s.gate_failures)) or "<span class=mut>clear</span>",
            ])
        body.append(table(["Product", "Name", "Score", "Verdict", "Window", "Gate failures"],
                          rows, num_cols={2}))
    else:
        body.append("<p class=mut>No scores yet — run <code>daily</code> after importing data.</p>")
    body.append("</div>")
    return page("Overview", "".join(body), "/")


def page_product(db: Database, pid: str) -> Optional[str]:
    product = db.get_product(pid)
    if product is None:
        return None
    body = [f"<h1>{esc(product.name)} <span class=mut>({esc(pid)})</span></h1>"]

    step = next_step(db, product)
    body.append(f"<blockquote><b>Next:</b> {esc(step.action)}"
                + (f"<br><code>{esc(step.command)}</code>" if step.command else "")
                + "</blockquote>")

    sr = pipeline.score_stored(db, pid)
    if sr is not None:
        body.append(f"<div class=panel>{md_to_html(render_scorecard(sr))}</div>")
    else:
        body.append("<div class=panel><p class=mut>No metrics yet — nothing to score.</p></div>")

    creatives = db.creatives_for(pid)
    if creatives:
        body.append("<h2>Creatives</h2><div class=panel>")
        rows = [[esc(c.id), esc(c.format), esc(c.hook[:60]), esc(c.status),
                 ("✓" if c.meta.get("aigc_disclosure") else "<span class=bad>missing</span>")]
                for c in creatives]
        body.append(table(["ID", "Format", "Hook", "Status", "AIGC disclosure"], rows))
        body.append("</div>")

    tests = db.tests_for_product(pid)
    if tests:
        body.append("<h2>Live test telemetry</h2><div class=panel>")
        rows = [[esc(t.date), f"${t.spend:.2f}",
                 f"${t.spend * (t.roas or 0):.2f}", f"{t.roas or 0:.2f}"]
                for t in sorted(tests, key=lambda t: t.date)]
        body.append(table(["Date", "Spend", "Revenue", "ROAS"], rows, num_cols={1, 2, 3}))
        body.append("</div>")
    return page(pid, "".join(body), "/")


def page_advertising(db: Database) -> str:
    body = ["<h1>Advertising</h1>"]

    # ── Higgsfield / MCP configuration status ──────────────────────────────────
    mcp_ok = bool(CONFIG.higgsfield_mcp_url)
    soul_ok = bool(CONFIG.higgsfield_soul_id)
    llm_ok = CONFIG.llm_available
    body.append("<h2>Creative pipeline configuration</h2><div class=panel>")
    body.append(table(["Setting", "Status", "What it does"], [
        ["<code>HIGGSFIELD_MCP_URL</code>",
         "<span class=good>configured</span>" if mcp_ok
         else "<span class=warn>not set — dry-run mode</span>",
         "The MCP endpoint that generates video batches. Unset = plans only."],
        ["<code>HIGGSFIELD_MCP_TOOL</code>", f"<code>{esc(CONFIG.higgsfield_mcp_tool)}</code>",
         "Tool name called for each generation job."],
        ["<code>HIGGSFIELD_SOUL_ID</code>",
         f"<code>{esc(CONFIG.higgsfield_soul_id)}</code>" if soul_ok
         else "<span class=warn>not set</span>",
         "ONE persona per store, reused across every ad."],
        ["<code>ANTHROPIC_API_KEY</code>",
         "<span class=good>configured</span>" if llm_ok
         else "<span class=warn>offline fallback</span>",
         "Psychology + hooks/scripts quality (LLM pass vs deterministic)."],
    ]))
    body.append("<p class=mut>Set these in <code>.env</code> next to the repo, then restart "
                "the server. Generation always requires an explicit "
                "<code>creative &lt;id&gt; --confirm</code> in the terminal — the dashboard "
                "never spends money.</p></div>")

    # ── Creative batches per product ───────────────────────────────────────────
    body.append("<h2>Creative batches</h2><div class=panel>")
    any_creatives = False
    rows = []
    for p in db.all_products():
        creatives = [c for c in db.creatives_for(p.id) if c.format != "Manual"]
        if not creatives:
            continue
        any_creatives = True
        by_status: dict[str, int] = {}
        for c in creatives:
            by_status[c.status] = by_status.get(c.status, 0) + 1
        missing = sum(1 for c in creatives if not c.meta.get("aigc_disclosure"))
        rows.append([
            f"<a href='/product?id={esc(p.id)}'>{esc(p.id)}</a>",
            str(len(creatives)),
            esc(", ".join(f"{n} {s}" for s, n in sorted(by_status.items()))),
            (f"<span class=bad>{missing} missing</span>" if missing
             else "<span class=good>all present</span>"),
        ])
    if any_creatives:
        body.append(table(["Product", "Creatives", "Status", "AIGC disclosure"], rows,
                          num_cols={1}))
    else:
        body.append("<p class=mut>No creative batches yet. When a product hits TEST, run "
                    "<code>creative &lt;id&gt;</code> (dry-run is free).</p>")
    body.append("</div>")

    # ── Live ad tests vs break-even ────────────────────────────────────────────
    body.append("<h2>Live ad tests</h2><div class=panel>")
    rows = []
    for p in db.all_products():
        tests = db.tests_for_product(p.id)
        if not tests:
            continue
        summary = summarize_tests(p.id, tests)
        suppliers = db.suppliers_for(p.id)
        metrics = db.metrics_for(p.id)
        be = float("inf")
        if suppliers and metrics:
            from ..economics import compute_economics
            best = min(suppliers, key=lambda s: s.cost + s.ship_cost)
            be = compute_economics(metrics[-1].price, best.cost, best.ship_cost).breakeven_roas
        hours, _ = hours_below_breakeven(tests, be)
        timer = (f"<span class=bad>{hours:.0f}h / {KILL_HOURS:.0f}h</span>" if hours
                 else "<span class=good>clear</span>")
        roas = summary.avg_roas or 0
        roas_cell = (f"<span class={'good' if roas >= be else 'bad'}>{roas:.2f}</span>"
                     if be != float("inf") else f"{roas:.2f}")
        rows.append([f"<a href='/product?id={esc(p.id)}'>{esc(p.id)}</a>",
                     f"${summary.spend:.0f}", roas_cell,
                     f"{be:.2f}" if be != float("inf") else "—", timer])
    if rows:
        body.append(table(["Product", "Spend", "Avg ROAS", "Break-even", "48h kill timer"],
                          rows, num_cols={1, 2, 3}))
    else:
        body.append("<p class=mut>No live tests. Log daily with "
                    "<code>log-test &lt;id&gt; --spend X --revenue Y</code>.</p>")
    body.append("</div>")
    return page("Advertising", "".join(body), "/advertising")


def page_budget(db: Database, q: dict) -> str:
    body = ["<h1>Budget</h1>"]

    # ── current burn from logged tests ─────────────────────────────────────────
    week_ago = (_date.today() - timedelta(days=7)).isoformat()
    burn = 0.0
    for p in db.all_products():
        burn += sum(t.spend for t in db.tests_for_product(p.id) if t.date >= week_ago)
    body.append("<div class=kpis>" + kpi(f"${burn:,.0f}", "ad spend logged, last 7 days")
                + "</div>")

    # ── capital / cash-flow calculator ─────────────────────────────────────────
    cap = _f(q, "capital", 5000.0)
    tb = _f(q, "test_budget", 300.0)
    lag = _f(q, "payout_lag", 14.0)
    dad = _f(q, "daily_ad", 50.0)
    dcogs = _f(q, "daily_cogs", 30.0)
    fixed = _f(q, "monthly_fixed", 0.0)
    plan = plan_capital(capital=cap, test_budget=tb, payout_lag_days=lag,
                        daily_ad_spend=dad, daily_cogs=dcogs, monthly_fixed=fixed)
    body.append("<h2>Capital &amp; cash flow (TikTok Shop)</h2><div class=panel>"
                "<form class=calc method=get action=/budget>"
                f"<label>Capital $<input name=capital value='{cap:g}'></label>"
                f"<label>Test budget $<input name=test_budget value='{tb:g}'></label>"
                f"<label>Payout lag (days)<input name=payout_lag value='{lag:g}'></label>"
                f"<label>Daily ad $<input name=daily_ad value='{dad:g}'></label>"
                f"<label>Daily COGS $<input name=daily_cogs value='{dcogs:g}'></label>"
                f"<label>Monthly fixed $<input name=monthly_fixed value='{fixed:g}'></label>"
                "<button>Recalculate</button></form>"
                f"<pre>{esc(plan.summary)}</pre>"
                "<p class=mut>Tracking only — the spend decision stays yours.</p></div>")

    # ── Etsy POD listings calculator ───────────────────────────────────────────
    tgt = _f(q, "pod_target", 1000.0)
    pps = _f(q, "pod_profit", 8.0)
    spl = _f(q, "pod_spl", 0.3)
    cur = _i(q, "pod_current", 0)
    hrs = _f(q, "pod_hours", 5.0)
    mins = _f(q, "pod_minutes", 30.0)
    body.append("<h2>Etsy print-on-demand — how many listings?</h2><div class=panel>"
                "<form class=calc method=get action=/budget>"
                f"<label>Target profit $/mo<input name=pod_target value='{tgt:g}'></label>"
                f"<label>Profit per sale $<input name=pod_profit value='{pps:g}'></label>"
                f"<label>Sales / listing / mo<input name=pod_spl value='{spl:g}'></label>"
                f"<label>Listings live now<input name=pod_current value='{cur}'></label>"
                f"<label>Hours per week<input name=pod_hours value='{hrs:g}'></label>"
                f"<label>Min per listing<input name=pod_minutes value='{mins:g}'></label>"
                "<button>Recalculate</button></form>")
    try:
        pod = plan_pod(target_monthly_profit=tgt, profit_per_sale=pps,
                       sales_per_listing_month=spl, current_listings=cur,
                       hours_per_week=hrs, minutes_per_listing=mins)
        body.append(f"<pre>{esc(pod.summary)}</pre>")
    except ValueError as e:
        body.append(f"<p class=bad>{esc(str(e))}</p>")
    body.append("<p class=mut>Profit per sale = sale price − POD base cost − Etsy fees "
                "(~9.5% incl. payment) − any ads. Measure your real sales/listing after "
                "30 days and re-plan.</p></div>")
    return page("Budget", "".join(body), "/budget")


def page_creators(db: Database) -> str:
    body = ["<h1>UGC &amp; affiliate creators</h1>",
            "<blockquote>The playbook: open an affiliate plan with 15–25% commission, "
            "invite 30–50 small creators (5k–100k) in your niche, send free samples to "
            "the 10 best responders, and iterate on whoever converts. The relationship "
            "stays human — the engine only preps the materials.</blockquote>"]

    body.append("<h2>Where to find creators</h2><div class=panel>")
    rows = [[f'<a href="{href}" target=_blank rel=noopener>{esc(name)}</a>', esc(note)]
            for name, href, note in CREATOR_LINKS]
    body.append(table(["Marketplace", "What it's for"], rows))
    body.append("</div>")

    ready = [s for s in db.board() if s.gates_passed and s.total >= CONFIG.score_threshold]
    body.append("<h2>What to send them</h2><div class=panel>")
    if ready:
        body.append("<p>TEST-ready products to pitch right now:</p><ul>")
        for s in ready:
            p = db.get_product(s.product_id)
            body.append(f"<li><a href='/product?id={esc(s.product_id)}'>"
                        f"{esc(p.name if p else s.product_id)}</a> — build the outreach "
                        f"packet: <code>python -m tt_engine.cli packet {esc(s.product_id)}"
                        f"</code></li>")
        body.append("</ul>")
    else:
        body.append("<p class=mut>No TEST-ready products yet — creator outreach starts "
                    "once something clears the gates at 80+.</p>")
    body.append("<p class=mut>The packet gives you the psychology spine, hooks, and the "
                "offer math — paste those into your creator brief so every video leads "
                "with the trigger that converts.</p></div>")
    return page("Creators", "".join(body), "/creators")


# ── HTTP plumbing ────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    db_path: str = CONFIG.db_path

    def do_GET(self):  # noqa: N802 (http.server API)
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            with Database(self.db_path) as db:
                if url.path == "/":
                    html = page_overview(db)
                elif url.path == "/product":
                    pid = (q.get("id") or [""])[0]
                    html = page_product(db, pid)
                    if html is None:
                        return self._send(404, page("Not found",
                                                    f"<h1>No product {esc(pid)}</h1>"))
                elif url.path == "/advertising":
                    html = page_advertising(db)
                elif url.path == "/budget":
                    html = page_budget(db, q)
                elif url.path == "/creators":
                    html = page_creators(db)
                else:
                    return self._send(404, page("Not found", "<h1>404</h1>"))
            self._send(200, html)
        except Exception as e:  # show the error instead of a hung tab (local tool)
            self._send(500, page("Error", f"<h1>Error</h1><pre>{esc(repr(e))}</pre>"))

    def _send(self, code: int, html: str) -> None:
        data = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # quiet by default
        pass


def make_server(db_path: str, host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"db_path": db_path})
    return ThreadingHTTPServer((host, port), handler)


def run(db_path: str, host: str = "127.0.0.1", port: int = 8787) -> None:
    srv = make_server(db_path, host, port)
    print(f"ENGINE dashboard → http://{host}:{srv.server_address[1]}  (Ctrl-C to stop)")
    print(f"DB: {db_path}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        srv.server_close()
