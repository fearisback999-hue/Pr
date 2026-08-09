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
from ..playbook import STEPS, VERIFIED_DATE, all_sources, current_phase, overall, progress
from ..reports.scorecard import render_scorecard, verdict
from ..validation import KILL_HOURS, hours_below_breakeven, summarize_tests
from .render import (
    chip, esc, kpi, md_to_html, meter, page, sparkline, stage_chip, table,
)

# Pricing verified 2026-07-09 via live web research — reverify before budgeting against
# it, these platforms change plans/pricing often. See docs/OPERATING.md for sources.
CREATOR_LINKS = [
    ("TikTok Shop Affiliate Center", "https://affiliate-us.tiktok.com",
     "Free. Open collaboration + targeted invites — the main channel for TikTok Shop "
     "affiliates; you only pay the commission rate you set, per sale."),
    ("TikTok Creator Marketplace", "https://creatormarketplace.tiktok.com",
     "Free to browse. TikTok's official creator search (audience size, engagement, "
     "categories)."),
    ("Collabstr", "https://collabstr.com",
     "Free to browse, 10% fee on bookings. Pro $299/mo or Premium $399/mo for advanced "
     "features. Good default starting point — no minimum spend."),
    ("Fiverr — UGC videos", "https://www.fiverr.com/search/gigs?query=ugc%20tiktok%20video",
     "Pay-per-gig, no subscription. Cheapest tier — good for volume-testing hooks "
     "before paying premium creators."),
    ("Billo", "https://billo.app",
     "~$99+/video, buy packs from a balance, bulk discounts. No monthly minimum."),
    ("Twirl", "https://www.twirl.so",
     "Self-serve from ~$325/video (full usage rights). Managed service from "
     "~$2,560/campaign if you want strategy support included."),
    ("Insense", "https://insense.pro",
     "Self-service plan from ~$500/mo (billed quarterly), + a 7–20% marketplace fee on "
     "creator payments depending on tier. Higher commitment — better once you know your "
     "angle works and want to scale UGC volume."),
    ("Upwork — UGC creators", "https://www.upwork.com/services/ugc",
     "Pay-per-project or hourly, no platform subscription. Best for a longer-term "
     "creator relationship once you've found someone who converts."),
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
    pb_done, pb_total = overall(db)
    body.append("<div class=kpis>"
                + kpi(str(len(scores)), "products scored")
                + kpi(str(attack), "TEST-ready now")
                + kpi(str(len(live_tests)), "products with live tests")
                + kpi(f"{CONFIG.score_threshold:.0f}", "score threshold")
                + kpi(f"{pb_done}/{pb_total}", "playbook steps")
                + "</div>")

    where = current_phase(db)
    if where:
        body.append(f"<blockquote>Business playbook: <b>{esc(where.name)}</b> "
                    f"({where.done_count}/{where.total}) — "
                    f"<a href='/playbook'>open the full checklist →</a></blockquote>")

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

    # ── Autopilot: the approval-gated automation queue ─────────────────────────
    pending = db.autopilot_actions(status="pending")
    body.append("<h2>Autopilot — automated, approval-gated</h2><div class=panel>")
    body.append("<p><a href='/autopilot/run'>↻ refresh proposals</a> — the engine "
                "proposes every next step; nothing runs until you approve it. "
                "<span class=mut>Safe (internal) steps approve right here; anything "
                "that spends money is CLI-only, always.</span></p>")
    if pending:
        rows = []
        for i in pending:
            if i["kind"] == "decision":
                act = (f"<a href='/autopilot/approve?id={i['id']}'><b>select ✓</b></a> · "
                       f"<a href='/autopilot/reject?id={i['id']}'>pass</a>")
            elif i["kind"] == "internal":
                act = (f"<a href='/autopilot/approve?id={i['id']}'>approve ▶</a> · "
                       f"<a href='/autopilot/reject?id={i['id']}'>reject</a>")
            elif i["kind"] == "external":
                act = (f"<span class=warn>spends money</span> — "
                       f"<code>autopilot approve {i['id']}</code> (CLI only)")
            else:
                act = "<span class=mut>yours to do — clears itself when done</span>"
            rows.append([f"#{i['id']}",
                         (f"<a href='/product?id={esc(i['product_id'])}'>"
                          f"{esc(i['product_id'])}</a>" if i["product_id"] else "—"),
                         esc(i["stage"]), esc(i["description"][:90]), act])
        body.append(table(["#", "Product", "Step", "What it does", "Decision"], rows))
    else:
        body.append("<p class=mut>Queue empty — hit refresh to propose next steps "
                    "from the live state.</p>")
    body.append("</div>")

    # ── Test queue: ranked by expected dollars, not points ─────────────────────
    from ..selection import rank_for_test
    srs = [sr for sr in (pipeline.score_stored(db, s.product_id) for s in scores) if sr]
    if srs:
        ranked = rank_for_test(srs)
        body.append("<h2>Test queue — ranked by expected value</h2><div class=panel>")
        rows = []
        for sr in ranked[:8]:
            sel, sid = sr.selection, sr.breakdown.score.product_id
            if sel.ev.eligible:
                ev_cell = f"<b>${sel.ev.ev:+,.0f}</b>"
                p_cell = f"{sel.ev.p_win:.0%}"
                fit_tag = (f" · AI-fit {sel.fit.score:.0%} ({sel.fit.band})"
                           if sel.fit else "")
                note = f"<span class=mut>fund in this order{esc(fit_tag)}</span>"
            else:
                ev_cell, p_cell = "—", "—"
                note = f"<span class=warn>{esc(sel.ev.reason)}</span>"
            needed = sel.ceiling.products_needed_for_100k
            rows.append([
                f"<a href='/product?id={esc(sid)}'>{esc(sid)}</a>",
                ev_cell, p_cell,
                f"${sel.ceiling.ceiling_monthly:,.0f}",
                f"×{needed}" if needed else "—",
                note,
            ])
        body.append(table(["Product", "EV / $200 test", "p(win)", "Ceiling $/mo",
                           "→ $100k mo", "Why / blocker"], rows, num_cols={1, 2, 3}))
        body.append("<p class=mut>EV = p(win)·payoff − p(lose)·loss at the TRUE fee "
                    "stack (referral + payment + affiliate). It orders the queue; the "
                    "48h kill timer still decides what happens after money moves. "
                    "<b>×N</b> = products of this ceiling needed for a $100k month "
                    "(<code>scale</code> shows that month itemized).</p></div>")

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


def page_launch(db: Database) -> str:
    """Day one to day thirty, in time order, with the money attached — and the live
    state of every guard that stands between you and an accidental spend."""
    from ..capital import plan_capital
    from ..creative import spend

    plan = plan_capital(capital=2000.0, test_budget=150.0,
                        daily_ad_spend=15.0, daily_cogs=7.0)
    unit, ceiling = spend.unit_cost(), spend.spend_ceiling()

    body = ["<h1>Launch — the first 30 days</h1>",
            "<p class=mut>The playbook groups the work by topic. This is the same work "
            "in time order, with the budget attached and the long-lead items pulled to "
            "the front. Full detail: <code>python -m tt_engine.cli launch</code></p>"]

    body.append("<div class=kpis>"
                + kpi(f"${plan.deployable:,.0f}", "deployable")
                + kpi(f"{plan.max_concurrent_tests}", "concurrent tests")
                + kpi(f"{plan.runway_months:.1f}mo", "runway")
                + kpi("$150", "per test")
                + "</div>")

    if plan.warnings:
        body.append("<div class=panel><p class=label>Capital warnings</p><ul>"
                    + "".join(f"<li>{esc(w)}</li>" for w in plan.warnings)
                    + "</ul></div>")

    # ── The money split ───────────────────────────────────────────────────────
    split = [("Reserve", 300, "Never spent. It is what makes month two exist."),
             ("Payout float", 310, "In transit — TikTok holds payouts ~14 days."),
             ("Tools, month one", 150, "Market data + generation subscriptions."),
             ("Samples", 60, "Three products, ~$20 each. Mandatory."),
             ("Product tests", 1180, "~7 at $150. The only money that buys information.")]
    rows = [[n, f"${a:,}", note] for n, a, note in split]
    body.append("<div class=panel><p class=label>How the $2,000 splits</p>"
                + table(["bucket", "amount", "rule"], rows)
                + "<p class=mut>Sized by running <code>capital</code> until it returns "
                "zero warnings. At $250/test the same $2,000 drops to a 1.5-month "
                "runway. You are buying attempts, not outcomes.</p></div>")

    # ── Spend guards: the live state of what protects you ─────────────────────
    guards = [
        ["Batch size cap", f"{spend.MAX_BATCH} clips", "armed",
         "Refuses above it — a 3,000-variation typo would be 3,000 paid jobs."],
        ["Unit cost", f"${unit:,.2f}/clip" if unit else "UNSET",
         "armed" if unit else "unset",
         "Set TT_GENERATION_UNIT_COST so the confirm prompt shows dollars, not just "
         "a warning that money moves."],
        ["Per-batch ceiling", f"${ceiling:,.2f}" if ceiling else "UNSET",
         "armed" if ceiling else "unset",
         "Set TT_MAX_BATCH_SPEND. Refuses an over-ceiling batch even with --confirm."],
        ["Double-spend guard", "always on", "armed",
         "Re-generating a spec that already has a job is refused — it would pay twice "
         "and overwrite the first job id."],
        ["Duplicate-post guard", "always on", "armed",
         "An already-posted asset cannot be posted again."],
        ["Job recovery", "always on", "armed",
         "Jobs are charged at submit. <code>creative-recover</code> collects assets you "
         "already paid for but never received."],
    ]
    grows = [[g[0], g[1],
              f'<span class="chip {"TEST" if g[2] == "armed" else "WATCH"}">{g[2]}</span>',
              g[3]] for g in guards]
    body.append("<div class=panel><p class=label>Spend guards</p>"
                + table(["guard", "setting", "state", "what it stops"], grows)
                + "</div>")

    orphans = [c for c in db.all_creatives()
               if c.status == "generating" and c.meta.get("job_id")]
    if orphans:
        body.append(f"<blockquote><b>{len(orphans)} job(s) submitted and paid for have "
                    "not landed.</b> They are tracked with their job ids. Run "
                    "<code>python -m tt_engine.cli creative-recover</code> to collect "
                    "them — do not re-generate, that pays twice.</blockquote>")

    # ── The sequence ──────────────────────────────────────────────────────────
    phases = [
        ("Day 1", "$0 out", "Paperwork, and the applications that take days",
         ["Deposit the $2,000 into a dedicated business account — not personal",
          "Get an EIN — free, instant, IRS.gov, one sitting (it times out)",
          "Decide the structure — sole prop is fastest, LLC separates your assets",
          "Apply for TikTok Shop Seller — the long pole, 1–3 business days",
          "Create a TikTok Ads Manager account (separate login)",
          "Open a supplier account — CJ, Zendrop, or AutoDS. Free",
          "Start the bookkeeping sheet, before the first transaction",
          "Tonight: read the prohibited-items list and the AI-disclosure rule"]),
        ("Days 2–4", "~$40 data", "Find three candidates",
         ["Get real market data in — import a CSV, or scout by hand for free",
          "Rank it: <code>daily</code> → <code>find --top 5</code> → <code>scorecard</code>",
          "Choose exactly three. Not one (no information), not ten (no focus)"]),
        ("Days 3–7", "~$60 samples", "Quotes out, samples ordered",
         ["Real landed-cost quote for each — <code>add-supplier</code>. No guesses",
          "Order all three samples TODAY — they take 5–10 days and gate everything",
          "Check the supplier against the shipping SLA — <code>health</code>"]),
        ("Days 5–10", "~$110 tools", "Build creative while the samples ship",
         ["Psychology pass on real comments — <code>psych</code>",
          "Pick your actor from the roster — one face per account",
          "Wire generation, then set the spend guards above before you confirm anything",
          "Draft specs and READ them, then <code>--confirm</code>. ~1 usable clip in 4",
          "Phone test every clip: arm's length, muted, full speed"]),
        ("Days 10–12", "decision point", "Samples arrive — a real gate",
         ["Hold each product. Does it do what the video is about to claim?",
          "Kill anything that disappoints you in your hands, before any ad money",
          "Create the listing; price off the margin floor, not vibes"]),
        ("Days 12–20", "$150 per product", "The first real test",
         ["Verify Pixel + Events API are firing BEFORE spending a dollar",
          "Launch small and spread — a few hooks, small per-ad-set budgets",
          "Log spend and revenue every single day — <code>log-test</code>",
          "At 48h let <code>validate</code> decide. Do not override it"]),
        ("Days 20–30", "from the test budget", "Iterate, then compound",
         ["Killed → next candidate, no mourning period",
          "Scaled → raise 20–30% at a time, re-validating after each raise",
          "Diversify creative before scaling hard — fatigue kills a single creative"]),
    ]
    for when, cost, title, items in phases:
        body.append(f"<div class=phasehead><h2 style='margin:0'>{esc(title)}</h2>"
                    f"<span class=n>{esc(when)} · {esc(cost)}</span></div>")
        body.append("<div class=panel><ul>"
                    + "".join(f"<li>{i}</li>" for i in items) + "</ul></div>")

    body.append("<blockquote><b>Month one is EV-negative by design</b> (~−$385 at this "
                "size). You are buying real cost data on three real products, a working "
                "pipeline, reps at killing losers fast, and an option on a winner. Most "
                "first tests lose — that is the base rate, not a verdict on you. "
                "<code>scale</code> prices the $100k month at $41,783 of working capital: "
                "$2,000 buys the first rung of the ladder, and each rung is funded by the "
                "one below it.</blockquote>")
    return page("Launch", "".join(body), "/launch")


def page_playbook(db: Database) -> str:
    """The zero-to-hero checklist: every step of the business, in order, with a live
    completion state. Auto steps flip themselves from DB state; manual steps toggle via
    a plain link (no money moves here — checking a box is always safe and reversible)."""
    phases = progress(db)
    done, total = overall(db)
    where = current_phase(db)

    body = ["<h1>Zero-to-hero playbook</h1>"]
    body.append("<div class=kpis>" + kpi(f"{done}/{total}", "steps complete")
                + kpi(where.name if where else "complete", "you are here")
                + "</div>")
    pct = int(100 * done / total) if total else 0
    body.append(f"<div class=panel><div class=bar><i style='width:{pct}%'></i></div>"
                f"<p class=mut>{pct}% of the whole business checklist — legal setup "
                "through scaling a winner. Auto steps (marked <code>auto</code>) check "
                "themselves off the moment the DB shows the work; manual steps "
                "(marked <code>manual</code>) you tick yourself once done off-engine.</p></div>")

    for p in phases:
        ppct = int(100 * p.done_count / p.total) if p.total else 0
        body.append(f"<div class=phasehead><h2 style='margin:0'>{esc(p.name)}</h2>"
                    f"<span class=n>{p.done_count}/{p.total}</span></div>")
        body.append(f"<div class=panel><div class=bar><i style='width:{ppct}%'></i></div>")
        for step, is_done in p.steps:
            if step.auto:
                box = "<div class=box>✓</div>" if is_done else "<div class=box>·</div>"
            else:
                nxt = 0 if is_done else 1
                box = (f"<div class=box><a href='/playbook/toggle?id={esc(step.id)}"
                       f"&amp;done={nxt}' title='toggle'>{'✓' if is_done else ''}</a></div>")
            cmd = (f"<div class=cmd><code>{esc(step.command)}</code></div>"
                  if step.command else "")
            src = "auto" if step.auto else "manual"
            cites = ""
            if step.sources:
                links = " · ".join(
                    f"<a href='{esc(u)}' target=_blank rel=noopener>source</a>"
                    if i == 0 else f"<a href='{esc(u)}' target=_blank rel=noopener>[{i+1}]</a>"
                    for i, u in enumerate(step.sources)
                )
                cites = f"<div class='cmd mut'>{links}</div>"
            body.append(
                f"<div class='pbstep{' done' if is_done else ''}'>{box}"
                f"<div class=body><b>{esc(step.title)}</b><span class=src>{src}</span>"
                f"<div class=mut>{esc(step.detail)}</div>{cmd}{cites}</div></div>"
            )
        body.append("</div>")

    sources = all_sources()
    if sources:
        body.append(f"<h2>Sources (verified {VERIFIED_DATE})</h2><div class=panel>")
        body.append("<p class=mut>Concrete facts above (fees, thresholds, SLAs, windows) "
                    "were pulled from these — re-check before relying on anything money- "
                    "or compliance-critical, platforms change terms without much "
                    "notice.</p><ul>")
        body.extend(
            f"<li><a href='{esc(u)}' target=_blank rel=noopener>{esc(u)}</a></li>"
            for u in sources
        )
        body.append("</ul></div>")
    return page("Playbook", "".join(body), "/playbook")


def playbook_toggle(db: Database, step_id: str, done: bool) -> Optional[str]:
    """Apply a manual toggle from the dashboard. Returns None for an unknown/auto step
    (nothing to toggle), else the step id that was set."""
    step = next((s for s in STEPS if s.id == step_id), None)
    if step is None or step.auto is not None:
        return None
    db.set_playbook_step(step_id, done)
    return step_id


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
        # Lifecycle + confidence + trend — the at-a-glance read above the full scorecard.
        metrics = db.metrics_for(pid)
        units = [float(m.units) for m in metrics][-35:]
        body.append("<div class=panel>"
                    f"<p>{stage_chip(sr.lifecycle.stage)} "
                    f"<span class=mut>{esc('; '.join(sr.lifecycle.reasons[:1]))}</span></p>"
                    f"<p><b>Units/day (last {len(units)}d)</b><br>{sparkline(units)}</p>"
                    f"<p><b>Data confidence: {sr.confidence.score:.0%} "
                    f"({sr.confidence.band})</b>{meter(sr.confidence.score, 'confidence')}"
                    + ("".join(f"<div class=mut>• {esc(r)}</div>"
                               for r in sr.confidence.reasons) or
                       "<div class=mut>no data-quality gaps</div>")
                    + "</p></div>")
        # Selection math: what this product is WORTH funding, and what it can carry.
        sel = sr.selection
        fit_html = ""
        if sel.fit:
            fit_html = (f"<p>{esc(sel.fit.summary)}</p>"
                        + "".join(f"<div class=mut>✋ never: {esc(n)}</div>"
                                  for n in sel.fit.never_for)
                        + f"<p class=mut><code>ai-plan {esc(pid)}</code> prints the "
                        "persona's full advertising plan; "
                        f"<code>production {esc(pid)}</code> prints the step-by-step "
                        "video runbook (actor → frames → animate → voice → assemble).</p>")
        body.append("<div class=panel><p><b>Selection math</b></p>"
                    f"<p>{esc(sel.ev.summary)}</p>"
                    f"<p class=mut>{esc(sel.ceiling.summary)}</p>"
                    + "".join(f"<div class=mut>⚠ {esc(n)}</div>"
                              for n in sel.ceiling.notes)
                    + fit_html
                    + "</div>")
        body.append(f"<div class=panel>{md_to_html(render_scorecard(sr))}</div>")
    else:
        body.append("<div class=panel><p class=mut>No metrics yet — nothing to score.</p></div>")

    suppliers = db.suppliers_for(pid)
    if suppliers:
        from ..sourcing import rank_suppliers
        ranked = rank_suppliers(suppliers)
        body.append("<h2>Suppliers (best first)</h2><div class=panel>")
        rows = []
        for i, ss in enumerate(ranked):
            s = ss.supplier
            rows.append([("★ " if i == 0 else "") + esc(s.name or s.ref),
                         f"${s.cost:.2f}+${s.ship_cost:.2f}", f"{s.ship_days:.0f}d",
                         "US" if s.us_warehouse else "—", f"{ss.total:.0f}/100"])
        body.append(table(["Supplier", "Landed", "Ship", "Warehouse", "Score"], rows,
                          num_cols={1, 2, 4}))
        body.append("<p class=mut>★ = recommended (composite of cost, speed, reliability "
                    "— the same ranking `packet` uses). Need a US/fast supplier? See the "
                    "<a href='/ideas'>sourcing guide</a> (or <code>sourcing-guide</code>) "
                    "— the score rewards a US warehouse + sub-5-day shipping.</p></div>")
    else:
        body.append("<h2>Suppliers</h2><div class=panel><p class=mut>No supplier quote "
                    "yet — economics can't score without a real landed cost. Find a "
                    "US/fast supplier (<a href='/ideas'>sourcing guide</a>), order a "
                    "sample, then <code>add-supplier " + esc(pid) + " --cost X "
                    "--ship-cost Y --ship-days N --us-warehouse</code>.</p></div>")

    # ── Video specs: the 3 editable parts, reviewed before any spend ────────────
    specs = db.video_specs(pid)
    body.append("<h2>Video specs — edit before you generate</h2><div class=panel>")
    body.append("<p class=mut>Every generation is 3 separately-editable parts — "
                "actor · product · prompt. Fix any part here (via the shown command) "
                "and review the assembled result BEFORE generating, so a bad prompt "
                "costs no credits. New: <code>draft new " + esc(pid)
                + " --actor &lt;slug&gt;</code></p>")
    body.append(f"<p><a href='/actors/variants?product={esc(pid)}'>"
                "＋ Test demographics: one spec per actor →</a> "
                "<span class=mut>the legit way to target different people (old/young, "
                "etc.) — the same concept across YOUR roster, your own content.</span>"
                "</p>")
    if specs:
        from ..creative import resolve_actor
        rows = []
        for sp in specs:
            actor = resolve_actor(sp["actor_slug"])
            rows.append([f"#{sp['id']}",
                         esc(actor.name if actor else sp["actor_slug"] or "(default)"),
                         esc(sp["shot_mode"]), esc(sp["status"]),
                         esc(sp["prompt"][:70] + ("…" if len(sp["prompt"]) > 70 else ""))])
        body.append(table(["Spec", "Actor", "Mode", "Status", "Prompt (editable)"], rows))
        body.append("<p class=mut>Edit: <code>draft set &lt;id&gt; --prompt \"...\"</code> "
                    "(or <code>--actor</code> / <code>--mode</code>) · review: "
                    "<code>draft show &lt;id&gt;</code> · approve: <code>draft approve "
                    "&lt;id&gt;</code> · then generate the fixed version: "
                    "<code>draft generate &lt;id&gt; --confirm</code> (the only step "
                    "that spends credits).</p>")
    else:
        body.append("<p class=mut>No specs yet for this product.</p>")
    body.append("</div>")

    creatives = db.creatives_for(pid)
    if creatives:
        body.append("<h2>Creatives</h2><div class=panel>")
        rows = []
        for c in creatives:
            disc = c.meta.get("aigc_disclosure")
            if c.status == "posted":
                post = "<span class=good>posted</span>"
            elif c.status in ("exported", "ready") and disc:
                # Post from the app — a deliberate 2-step (confirm before it goes public).
                post = f"<a href='/publish?id={esc(c.id)}'>Post ▶</a>"
            else:
                post = "<span class=mut>export first</span>"
            rows.append([esc(c.id), esc(c.format), esc(c.hook[:52]), esc(c.status),
                         ("✓" if disc else "<span class=bad>missing</span>"), post])
        body.append(table(["ID", "Format", "Hook", "Status", "AIGC", "Post"], rows))
        body.append("<p class=mut>Posting uses TikTok's OFFICIAL Content Posting API "
                    "with your per-post permission — never a gray-market auto-poster. "
                    "Only exported, disclosure-carrying assets can post.</p></div>")

    tests = db.tests_for_product(pid)
    if tests:
        body.append("<h2>Live test telemetry</h2><div class=panel>")
        rows = [[esc(t.date), f"${t.spend:.2f}",
                 f"${t.spend * (t.roas or 0):.2f}", f"{t.roas or 0:.2f}"]
                for t in sorted(tests, key=lambda t: t.date)]
        body.append(table(["Date", "Spend", "Revenue", "ROAS"], rows, num_cols={1, 2, 3}))
        body.append("</div>")
    return page(pid, "".join(body), "/")


def page_actors(db: Database, use_slug: str = "") -> str:
    """The actor roster as a hub: every AI creator you've built, each on its own
    account. Click one to create a video with them — pick a product and the engine
    starts an editable spec (actor + product + prompt) you fix before generating."""
    from ..creative.persona import load_personas, persona_by_slug, validate_persona
    roster = load_personas()
    body = ["<h1>Actors</h1>",
            "<blockquote>Your roster of AI creators, each posting from its OWN account. "
            "Click <b>Create with…</b> on an actor, pick a product, and the engine "
            "starts an editable video spec (actor · product · prompt) you fix before "
            "spending any credits. Add more as <code>docs/persona/*.md</code> "
            "files.</blockquote>"]
    if not roster:
        body.append("<div class=panel><p class=mut>No actors yet. The shipped template "
                    "is <code>docs/persona/CREATOR.md</code>; copy it to add more.</p></div>")
        return page("Actors", "".join(body), "/actors")

    chosen = persona_by_slug(use_slug) if use_slug else None

    if chosen is None:
        # The roster grid — pick an actor to create with.
        body.append("<div class=grid>")
        for p in roster:
            ready = not validate_persona(p)
            initial = esc(p.name[:1].upper())
            status = ("<span class=good>ready</span>" if ready
                      else "<span class=warn>needs setup</span>")
            body.append(
                f"<div class=card><div class=crow>"
                f"<span class=avatar>{initial}</span>"
                f"<div><div class=nm>{esc(p.name)}</div>"
                f"<div class=mut style='font-size:12px'>{esc(p.account or 'no account set')}"
                f"</div></div></div>"
                f"<p class=mut style='min-height:34px'>rooms: "
                f"{esc(', '.join(p.settings) or '—')}</p>"
                f"<p>{status} · <a href='/actors?use={esc(p.slug)}'>"
                "<b>Create with " + esc(p.name) + " →</b></a></p></div>")
        body.append("</div>")
        return page("Actors", "".join(body), "/actors")

    # A specific actor chosen — the FULL character profile: look, rooms, voice, and
    # the create-a-spec picker. Everything that defines the character, in one place.
    p = chosen
    warns = validate_persona(p)
    body.append(f"<div class=crow style='margin:8px 0 4px'>"
                f"<span class=avatar>{esc(p.name[:1].upper())}</span>"
                f"<div><div class=nm style='font-size:22px'>{esc(p.name)}</div>"
                f"<div class=mut>{esc(p.account or 'no account set')}</div></div></div>")

    def field(label, value):
        return (f"<tr><td style='color:var(--faint);white-space:nowrap;"
                f"text-transform:uppercase;font-size:11px;letter-spacing:.05em'>"
                f"{esc(label)}</td><td>{value}</td></tr>")

    # ── Look (appearance) ───────────────────────────────────────────────────────
    body.append("<h2>What they look like</h2><div class=panel><table><tbody>")
    body.append(field("master", esc(p.master_description) or
                      "<span class=warn>not set</span>"))
    if p.forbidden:
        body.append(field("never changes", esc("; ".join(p.forbidden))))
    for slot, outfit in sorted(p.outfits.items()):
        body.append(field(slot.replace("outfit-", "outfit "), esc(outfit)))
    if p.jewelry:
        body.append(field("jewelry", esc(p.jewelry)))
    body.append("</tbody></table></div>")

    # ── Their rooms ─────────────────────────────────────────────────────────────
    body.append("<h2>Their rooms</h2><div class=panel>")
    if p.settings:
        body.append("<p>" + " · ".join(f"<code>{esc(s)}</code>" for s in p.settings)
                    + "</p><p class=mut>Their videos never leave these rooms (scene "
                    "coherence keeps it from looking generated).</p>")
    else:
        body.append("<p class=warn>No rooms set — add a <code>## settings</code> list.</p>")
    body.append("</div>")

    # ── Voice + lip-sync (the operator's concern) ───────────────────────────────
    body.append("<h2>Their voice &amp; lip-sync</h2><div class=panel>")
    body.append("<table><tbody>")
    body.append(field("voice", esc(p.voice_description) or
                      "<span class=warn>describe it in the bible</span>"))
    body.append(field("reference clip", (f"<code>{esc(p.voice_reference)}</code>"
                      if p.voice_reference else
                      "<span class=warn>none — pin ONE ≤15s clip</span>")))
    body.append("</tbody></table>")
    body.append("<p><b>Voice is as important as the face</b> — a shifting voice reads "
                "as AI instantly. Pin ONE voice and reuse it forever: record or "
                "generate a single ≤15s clip. To make the mouth match (so it doesn't "
                "look AI), lip-sync THAT voice onto the generated clips with "
                "ElevenLabs <b>video-to-voice</b>; use <b>text-to-voice</b> (same "
                "voice) for any narration. The <code>production &lt;id&gt;</code> "
                "runbook spells out these exact steps per scene.</p></div>")

    # ── Edit / status ───────────────────────────────────────────────────────────
    fname = p.source_path.split("/")[-1] if p.source_path else f"{p.slug}.md"
    body.append("<div class=panel><p><b>Edit this character:</b> everything above lives "
                f"in <code>docs/persona/{esc(fname)}</code> — change the look, rooms, "
                "or voice there and the app updates live. New character: "
                "<code>persona new \"Name\"</code>.</p>")
    if warns:
        body.append("<p class=warn>Before production:</p><ul>"
                    + "".join(f"<li>{esc(w)}</li>" for w in warns) + "</ul>")
    else:
        body.append("<p class=good>✓ Production-ready.</p>")
    body.append("</div>")

    # ── Create a video with this actor ──────────────────────────────────────────
    body.append("<h2>Create a video with " + esc(p.name) + "</h2><div class=panel>"
                "<p class=mut>Pick a product — a new editable spec opens on that "
                "product's page.</p>")
    products = db.all_products()
    if products:
        scored = {s.product_id: s for s in db.board()}
        rows = []
        for pr in products:
            sc = scored.get(pr.id)
            v = verdict(sc.gates_passed, sc.total) if sc else "—"
            rows.append([
                f"<a href='/product?id={esc(pr.id)}'>{esc(pr.id)}</a>",
                esc(pr.name), esc(pr.category), chip(v) if sc else "—",
                f"<a href='/actors/new?actor={esc(chosen.slug)}&amp;product={esc(pr.id)}'>"
                "<b>＋ create spec</b></a>"])
        body.append(table(["Product", "Name", "Category", "Verdict", ""], rows))
    else:
        body.append("<p class=mut>No products yet — add or import some first.</p>")
    body.append(f"<p class=mut><a href='/actors'>← all actors</a></p></div>")
    return page("Actors", "".join(body), "/actors")


def page_publish(db: Database, creative_id: str, confirm: bool) -> str:
    """Post from the app — a deliberate 2-step so a public post is never one accidental
    click away. Step 1 (no confirm): a confirmation panel. Step 2 (confirm=1): the
    OFFICIAL-API post with your permission, then the honest result."""
    from .. import publishing
    c = db.get_creative(creative_id)
    if c is None:
        return page("Post", "<h1>Post</h1><p class=bad>No such creative.</p>", "/")
    prod = f"/product?id={esc(c.product_id)}"
    if not confirm:
        body = [
            "<h1>Post to TikTok?</h1>",
            f"<div class=panel><p>About to post <b>{esc(c.id)}</b> "
            f"({esc(c.format)}) publicly to your TikTok account, via the OFFICIAL "
            "Content Posting API — your per-post permission. The AIGC label travels "
            "with it.</p>",
            f"<p><a href='/publish?id={esc(c.id)}&amp;confirm=1'>"
            "<b>Yes, post it ▶</b></a>  ·  "
            f"<a href='{prod}'>Cancel</a></p>",
            "<p class=mut>This is TikTok's sanctioned API, not a gray-market "
            "auto-poster. Posting is public and hard to undo, so it takes this "
            "deliberate second step.</p></div>",
        ]
        return page("Post", "".join(body), "/")
    # Confirmed: attempt the sanctioned post.
    try:
        res = publishing.publish_creative(db, c.id, confirm=True)
        note = res.summary + (" — " + "; ".join(res.notes) if res.notes else "")
        cls = "good" if res.posted else "warn"
    except publishing.PostingNotWired as e:
        note, cls = str(e), "warn"
    except ValueError as e:
        note, cls = str(e), "bad"
    body = [f"<h1>Post — {esc(c.id)}</h1>",
            f"<div class=panel><p class={cls}>{esc(note)}</p>",
            f"<p class=mut>Back to <a href='{prod}'>the product</a>.</p></div>"]
    return page("Post", "".join(body), "/")


def page_ideas(db: Database) -> str:
    """Product options — a menu of researched directions to validate, with the honest
    'not guaranteed winners' framing and the validation gate."""
    from .. import discovery, product_ideas
    from ..sourcing.guide import render as sourcing_render
    body = ["<h1>Product options</h1>",
            "<blockquote>Options, not one product at a time — a spread of archetypes "
            "that fit the model. These are <b>directions to validate with real data</b>, "
            "not guaranteed winners. Pick 2–3 that fit you, confirm demand + margin, "
            "then run them through the engine (<code>import-csv</code> → "
            "<code>daily</code> → <code>scorecard</code>).</blockquote>"]
    # How finding actually works + the scout workflow (the thing operators misread).
    body.append("<h2>How finding works &amp; where to scout</h2>")
    body.append(f"<div class=panel>{md_to_html(discovery.render())}</div>")
    body.append("<h2>Where to source (US / fast handling)</h2>")
    body.append(f"<div class=panel>{md_to_html(sourcing_render())}</div>")
    body.append("<h2>Product option menu</h2>")
    body.append(f"<div class=panel>{md_to_html(product_ideas.render())}</div>")
    body.append("<div class=panel><h2>Sources (verified 2026-07)</h2><ul>"
                + "".join(f"<li><a href='{esc(u)}' target=_blank rel=noopener>{esc(u)}"
                          "</a></li>" for u in product_ideas.SOURCES) + "</ul></div>")
    return page("Ideas", "".join(body), "/ideas")


def page_organic(db: Database) -> str:
    """Everything about organic marketing: the algorithm signals + the plays, plus the
    authenticity guide (they're the same job — native-feeling content that gets watched)."""
    from .. import organic_marketing
    from ..creative.realism import render_authenticity_guide
    body = ["<h1>Organic marketing</h1>"]
    body.append(f"<div class=panel>{md_to_html(organic_marketing.render())}</div>")
    body.append("<h2>Make the AI video look authentic</h2>")
    body.append(f"<div class=panel>{md_to_html(render_authenticity_guide())}</div>")
    body.append("<div class=panel><h2>Sources (verified 2026-07)</h2><ul>"
                + "".join(f"<li><a href='{esc(u)}' target=_blank rel=noopener>{esc(u)}"
                          "</a></li>" for u in organic_marketing.SOURCES) + "</ul></div>")
    return page("Organic", "".join(body), "/organic")


def page_styles(db: Database) -> str:
    """One tab per product TYPE: how clothing, gadgets, beauty, pet, home, hobby,
    accessories, toys, and wellness each get their own hooks, demo grammar, camera,
    rooms, and slideshow lead — sameness across categories is an AI tell."""
    from ..creative.category_styles import all_styles

    products = db.all_products()
    by_cat: dict[str, list] = {}
    for p in products:
        from ..creative.category_styles import style_for
        by_cat.setdefault(style_for(p.category).key, []).append(p)

    body = ["<h1>Category styles</h1>",
            "<blockquote>Every product type films differently — a try-on, a gadget "
            "demo, and a pet unboxing must not look like the same account made "
            "them. These styles drive the hooks, video prompts, and slideshows "
            "automatically: <code>creative-pack</code>, <code>production</code>, and "
            "<code>slideshows</code> all read them from the product's category. The "
            "AIGC label stays on every post regardless of style.</blockquote>"]

    for st in all_styles():
        mine = by_cat.get(st.key, [])
        live = (" · ".join(f"<a href='/product?id={esc(p.id)}'>{esc(p.id)}</a>"
                           for p in mine) if mine
                else "<span class=mut>no products in this category yet</span>")
        hook_samples = "".join(
            f"<li>[{esc(t)}] {esc(tmpl.replace('{name}', 'product').replace('{pain}', 'the pain'))}</li>"
            for t, tmpl in st.hook_templates[:4])
        body.append(f"<h2>{esc(st.label)}</h2><div class=panel>")
        body.append(f"<p><b>Your products:</b> {live}</p>")
        body.append(table(["What", "This category's way"], [
            ["Demo grammar", esc(st.demo_grammar)],
            ["Demo camera", esc(st.camera_demo) or "<span class=mut>engine default</span>"],
            ["Product handling", esc(st.interaction) or "<span class=mut>engine default</span>"],
            ["Rooms", esc(", ".join(st.setting_bias)) or "<span class=mut>any of the persona's rooms</span>"],
            ["Slideshow demo slide", esc(st.slideshow_lead) or "<span class=mut>rotating pool</span>"],
            ["Honest proof", esc(st.proof)],
        ]))
        if st.wardrobe_rule == "product-is-outfit":
            body.append("<p><b>Wardrobe rule:</b> the product IS the outfit — the "
                        "persona's pinned wardrobe steps aside for the garment "
                        "being sold (jewelry continuity stays).</p>")
        if st.garment_swap:
            body.append("<p><b>Fit-check method:</b> upload your real clothing "
                        "photo(s) — front/back angles — and the model is synthesized "
                        "wearing your EXACT garment (not a hallucination), in short "
                        "~8s try-on clips. <code>production &lt;id&gt;</code> on a "
                        "clothing product prints the full fit-check runbook.</p>")
        if st.dedicated_account:
            body.append(f"<p><b>Posting:</b> {esc(st.dedicated_account)}.</p>")
        if hook_samples:
            body.append(f"<p><b>Native hook angles:</b></p><ul>{hook_samples}</ul>")
        body.append("</div>")
    return page("Category styles", "".join(body), "/styles")


def page_advertising(db: Database) -> str:
    body = ["<h1>Advertising</h1>"]

    # ── Higgsfield configuration status ─────────────────────────────────────────
    hf_ok = CONFIG.higgsfield_available
    soul_ok = bool(CONFIG.higgsfield_soul_id)
    llm_ok = CONFIG.llm_available
    body.append("<h2>Creative pipeline configuration</h2><div class=panel>")
    body.append(table(["Setting", "Status", "What it does"], [
        ["<code>HIGGSFIELD_API_KEY</code> + <code>higgsfield-client</code> SDK",
         "<span class=good>configured</span>" if hf_ok
         else "<span class=warn>not set — dry-run mode</span>",
         "Scripted generation via the official SDK. Unset/not installed = plans only."],
        ["<code>HIGGSFIELD_SOUL_ID</code>",
         f"<code>{esc(CONFIG.higgsfield_soul_id)}</code>" if soul_ok
         else "<span class=warn>not set</span>",
         "ONE persona per store, reused across every ad."],
        ["<code>ANTHROPIC_API_KEY</code>",
         "<span class=good>configured</span>" if llm_ok
         else "<span class=warn>offline fallback</span>",
         "Psychology + hooks/scripts quality (LLM pass vs deterministic)."],
    ]))
    body.append(f"<p class=mut>Set these in <code>.env</code> next to the repo, then "
                f"restart the server. Alternative: running this from a Claude Code "
                f"session with the Higgsfield MCP connected "
                f"(<code>{esc(CONFIG.higgsfield_mcp_url)}</code>, browser OAuth, no API "
                f"key needed) — just ask the agent to generate the batch directly. "
                f"Either way, generation always requires an explicit "
                f"<code>creative &lt;id&gt; --confirm</code> in the terminal — the "
                f"dashboard never spends money.</p></div>")

    # ── AI creator program: the persona IS the ad engine ───────────────────────
    from ..creative.ai_creator import BOOST_DAYS, BOOST_TOP_N, POSTS_PER_DAY
    from ..creative.persona import load_persona, validate_persona
    bible = load_persona()
    bible_warn = validate_persona(bible)
    body.append("<h2>AI creator program — the persona is the ad engine</h2>"
                "<div class=panel>")
    if bible:
        status = ("<span class=good>production-ready</span>" if not bible_warn
                  else f"<span class=warn>{len(bible_warn)} gap(s) — run "
                       "<code>persona</code></span>")
    else:
        status = ("<span class=warn>missing — the shipped template is "
                  "<code>docs/persona/CREATOR.md</code></span>")
    body.append("<p><b>Creator bible:</b> "
                + (f"{esc(bible.name)} · {esc(bible.summary)} · " if bible else "")
                + status + "</p>")
    body.append(f"<p>One labeled persona (Soul ID), ~{POSTS_PER_DAY} posts/day, and a "
                "Spark loop: post organically for 48h, boost the top "
                f"{BOOST_TOP_N} posts for {BOOST_DAYS} days on the standard test "
                "budget, then let <code>validate</code>'s 48h kill timer decide. "
                "Every persona-driven sale keeps the affiliate commission a UGC "
                "creator would have earned.</p>"
                "<p><b>The honesty line the program runs on:</b> the persona may "
                "carry hooks, in-hand demos, styling, and replies — it may NEVER "
                "fabricate outcome proof (a generated 'result' is fabricated "
                "evidence; the AIGC label discloses the method, not that the "
                "outcome never happened). Outcome products get real affiliate "
                "footage; the persona frames it.</p>"
                "<p class=mut>Every product's <b>AI-creator fit</b> is scored on its "
                "page and folded into the EV test queue — the engine now selects "
                "FOR this distribution. <code>ai-plan &lt;id&gt;</code> prints the "
                "full per-product plan (fit, format mix, Spark loop, lane "
                "economics).</p></div>")

    # ── Actor roster: multiple actors, one account each ─────────────────────────
    from ..creative.persona import load_personas, validate_persona
    roster = load_personas()
    body.append("<h2>Actor roster — one account each</h2><div class=panel>")
    body.append(f"<p>{len(roster)} actor(s). Run a roster of ~10–12 personas, each "
                "posting from its OWN dedicated account — that multiplies shots at "
                "reach AND spreads the posting cadence so no single account looks "
                "automated. Add actors as <code>docs/persona/*.md</code> files.</p>")
    if roster:
        rows = [[esc(p.slug), esc(p.name), esc(p.account or "(no account set)"),
                 "<span class=good>ready</span>" if not validate_persona(p)
                 else f"<span class=warn>{len(validate_persona(p))} gap(s)</span>"]
                for p in roster]
        body.append(table(["Slug", "Name", "Account", "Bible"], rows))
        body.append("<p class=mut>Reference an actor in a video spec: "
                    "<code>draft new &lt;product&gt; --actor &lt;slug&gt;</code>.</p>")
    body.append("</div>")

    # ── Shot mode: the fallback ladder for when AI struggles ────────────────────
    from ..creative.realism import SHOT_MODES, shot_mode_spec
    cur_mode = db.get_setting("shot_mode", "full")
    body.append("<h2>Shot mode — the fallback when AI struggles</h2><div class=panel>"
                "<p>The face is the #1 AI failure and lip-sync the #2. If your "
                "generations look off, don't fight them — drop a tier and shoot "
                "AROUND them. Faceless (chest-down / hands / POV) removes both hard "
                "classes and often reads MORE real. Same product, label still on.</p>")
    rows = []
    for m in SHOT_MODES:
        spec = shot_mode_spec(m)
        on = (m == cur_mode)
        pick = (f"<b>current ✓</b>" if on
                else f"<a href='/shot-mode?set={m}'>use this</a>")
        rows.append([esc(spec["label"]), esc(spec["when"]), pick])
    body.append(table(["Mode", "When to use it", ""], rows))
    body.append("<p class=mut>Applies to <code>production</code> and fit-check "
                "runbooks; override per-run with <code>--mode</code>. Every mode "
                "keeps the AIGC label.</p></div>")

    # ── Account health / shadowban avoidance ────────────────────────────────────
    from .. import account_safety
    body.append("<h2>Account health — will a bot get us shadowbanned?</h2>"
                "<div class=panel>")
    body.append("<p><b>Not for LABELED AI content — but yes for automated account "
                "operation.</b> TikTok restricts reach for auto-posting via unofficial "
                "tools, bought/faked engagement, inhuman cadence, and coordinated "
                "accounts — not for AI videos that carry the disclosure. This engine "
                "never touches your account: it plans, <b>you</b> post from the app. "
                "Keep the human operation inside these lines.</p>")
    rows = [[esc(r.rule), esc(r.why)] for r in account_safety.RULES]
    body.append(table(["Do this", "Why (the signal it avoids)"], rows))
    body.append("<p class=mut><b>If reach suddenly drops:</b> "
                + esc(" · ".join(account_safety.REDUCED_REACH_PLAYBOOK[:4]))
                + f". Safe cadence ~1–{account_safety.SAFE_POSTS_PER_DAY} posts/day "
                "per established account; warm new accounts up first. "
                "<code>account-safety</code> prints the full guide.</p></div>")

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

    # ── month one: initial cash + expected profit ──────────────────────────────
    from ..capital import plan_month_one
    m1_tests = _i(q, "m1_tests", 2)
    m1_budget = _f(q, "m1_budget", 200.0)
    m1_prob = _f(q, "m1_prob", 0.20)
    m1_margin = _f(q, "m1_margin", 0.50)
    body.append("<h2>Month one — initial cash & honest expected profit</h2>"
                "<div class=panel><form class=calc method=get action=/budget>"
                f"<label>Ad tests<input name=m1_tests value='{m1_tests}'></label>"
                f"<label>$ per test<input name=m1_budget value='{m1_budget:g}'></label>"
                f"<label>Winner prob (0–1)<input name=m1_prob value='{m1_prob:g}'></label>"
                f"<label>True margin (0–1)<input name=m1_margin value='{m1_margin:g}'></label>"
                "<button>Recalculate</button></form>")
    try:
        m1 = plan_month_one(tests=m1_tests, test_budget=m1_budget,
                            winner_prob=m1_prob, true_margin=m1_margin)
        body.append(f"<pre>{esc(m1.summary)}</pre>")
    except ValueError as e:
        body.append(f"<p class=bad>{esc(str(e))}</p>")
    body.append("<p class=mut>The expected value is negative by design — month one buys "
                "data, reps, and the option on a winner. Anyone promising month-one "
                "profit is selling something.</p></div>")

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


def page_million(db: Database, q: dict) -> str:
    from ..roadmap import SOURCES, VERIFIED_DATE as RM_DATE, plan_million

    body = ["<h1>Road to $1M — the honest math</h1>",
            "<blockquote>Two different targets: <b>$1M revenue</b> (lifetime GMV — hard but "
            "reached by survivors) vs <b>$1M profit</b> (take-home — roughly top-1% "
            "execution). This computes what your target actually requires and places it in "
            "the real seller distribution. It sells nothing.</blockquote>"]

    goal = _f(q, "goal", 1_000_000.0)
    gtype = (q.get("type") or ["revenue"])[0]
    if gtype not in ("revenue", "profit"):
        gtype = "revenue"
    months = _i(q, "months", 24)
    aov = _f(q, "aov", 45.0)
    margin = _f(q, "margin", 0.16)
    pod = _i(q, "pod_listings", 0)

    body.append("<div class=panel><form class=calc method=get action=/million>"
                f"<label>Goal $<input name=goal value='{goal:.0f}'></label>"
                "<label>Type<input name=type value='" + esc(gtype) + "'></label>"
                f"<label>Horizon (months)<input name=months value='{months}'></label>"
                f"<label>AOV $<input name=aov value='{aov:g}'></label>"
                f"<label>Net margin (0–1)<input name=margin value='{margin:g}'></label>"
                f"<label>Etsy POD listings<input name=pod_listings value='{pod}'></label>"
                "<button>Recalculate</button></form>"
                "<p class=mut>Type = <code>revenue</code> or <code>profit</code>. Net margin "
                "~0.16 blended, ~0.35 organic-first (your own content, no affiliate cut).</p>"
                "</div>")

    try:
        plan = plan_million(goal_amount=goal, goal_type=gtype, horizon_months=months,
                            aov=aov, net_margin=margin, pod_listings=pod)
    except ValueError as e:
        body.append(f"<p class=bad>{esc(str(e))}</p>")
        return page("Road to $1M", "".join(body), "/million")

    body.append("<div class=kpis>"
                + kpi(f"${plan.monthly_revenue_needed:,.0f}", "revenue / month needed")
                + kpi(f"{plan.orders_per_day:.0f}", "orders / day")
                + kpi(str(plan.winners_needed), "winning products at scale")
                + kpi(f"${plan.monthly_ad_budget:,.0f}", "implied ad budget / mo")
                + "</div>")
    body.append(f"<div class=panel><p><b>Reality check:</b> {esc(plan.percentile)}</p>")
    if plan.notes:
        body.append("<ul>" + "".join(f"<li>{esc(n)}</li>" for n in plan.notes) + "</ul>")
    body.append("</div>")

    # milestone ladder
    body.append("<h2>Milestone ladder — survive the early rungs first</h2><div class=panel>")
    for m in plan.milestones:
        goalflag = (" <span class='chip TEST'>YOUR GOAL</span>" if m.is_goal else "")
        body.append(
            f"<div class=step><b>${m.monthly_revenue:,.0f}/mo — {esc(m.name)}</b>{goalflag}"
            f"<div class=mut>{esc(m.detail)}</div>"
            f"<div class=mut><i>odds: {esc(m.odds)}</i></div></div>"
        )
    body.append("</div>")

    # ── the $100k month, itemized ──────────────────────────────────────────────
    from ..roadmap import plan_scale
    scale_rev = _f(q, "scale_rev", 100_000.0)
    body.append("<h2>The $100k month, itemized</h2>")
    try:
        sp = plan_scale(monthly_revenue=scale_rev, aov=aov, net_margin=margin)
    except ValueError as e:
        body.append(f"<p class=bad>{esc(str(e))}</p>")
    else:
        body.append("<div class=kpis>"
                    + kpi(f"${sp.monthly_profit:,.0f}", "take-home / mo")
                    + kpi(str(sp.winners_needed), "concurrent winners")
                    + kpi(f"{sp.videos_per_week}", "videos / week")
                    + kpi(f"${sp.working_capital:,.0f}", "working capital to run it")
                    + "</div>")
        body.append("<div class=panel>")
        body.append(table(["Line item", "$/mo"], [
            ["Ad budget (fronted at 3.0× blended ROAS)", f"${sp.monthly_ad_budget:,.0f}"],
            ["COGS float (TikTok payout lag ~14d)", f"${sp.cogs_float:,.0f}"],
            ["Contingency (15%)", f"${sp.contingency:,.0f}"],
            ["<b>Working capital total</b>", f"<b>${sp.working_capital:,.0f}</b>"],
        ], num_cols={1}))
        body.append(f"<p class=mut>~{sp.orders_per_day:.0f} orders/day at "
                    f"${sp.aov:.0f} AOV · ~{sp.affiliates_target}+ active affiliates "
                    "(top-seller pattern). Change <code>scale_rev</code>, "
                    "<code>aov</code> or <code>margin</code> in the form above to "
                    "re-itemize.</p>")
        body.append("<ul>" + "".join(f"<li>{esc(n)}</li>" for n in sp.notes) + "</ul>")
        body.append("</div>")

    # the odds, plainly
    body.append("<h2>The odds, stated plainly</h2><div class=panel><ul>"
                "<li>Over half of all TikTok Shops are inactive; fewer than 10% of new "
                "sellers survive year one.</li>"
                "<li>Only ~1.5% of dropshipping stores ever earn more than $50k total; "
                "~1–5% build a sustainable business.</li>"
                "<li>The top 1% of US sellers drive ~60% of GMV; the median seller does "
                "~$1,150/mo. The distribution is brutally top-heavy.</li>"
                "<li>This engine doesn't beat those odds by magic — it compresses time and "
                "enforces discipline (real landed cost, the 45% margin gate, the 48h kill "
                "timer, tuned scoring). The near-certain payoff is the skill and the "
                "system; the $1M is the low-probability upside. Build for the former.</li>"
                "</ul></div>")

    body.append(f"<h2>Sources (verified {RM_DATE})</h2><div class=panel><ul>")
    body.extend(f"<li><a href='{esc(u)}' target=_blank rel=noopener>{esc(u)}</a></li>"
                for u in SOURCES)
    body.append("</ul></div>")
    return page("Road to $1M", "".join(body), "/million")


def page_search(db: Database, q: dict) -> str:
    query = (q.get("q") or [""])[0].strip()
    cat = (q.get("category") or [""])[0].strip()
    min_p = _f(q, "min_price", 0.0)
    max_p = _f(q, "max_price", 0.0)

    body = ["<h1>Search products</h1>",
            "<div class=panel><form class=calc method=get action=/search>"
            f"<label>Keyword<input name=q value='{esc(query)}'></label>"
            f"<label>Category<input name=category value='{esc(cat)}'></label>"
            f"<label>Min price $<input name=min_price value='{min_p:g}'></label>"
            f"<label>Max price $<input name=max_price value='{max_p:g}'></label>"
            "<button>Search</button></form>"
            "<p class=mut>Searches everything in YOUR database — imported CSVs, manual "
            "adds, and the sample feed. It does not (and by design will not) scrape "
            "TikTok/Amazon live; feed it exports and it searches them.</p></div>"]

    rows = []
    for p in db.all_products():
        if query and query.lower() not in p.name.lower() and query.lower() not in p.id.lower():
            continue
        if cat and p.category.lower() != cat.lower():
            continue
        metrics = db.metrics_for(p.id)
        price = metrics[-1].price if metrics else None
        if min_p and (price is None or price < min_p):
            continue
        if max_p and (price is None or price > max_p):
            continue
        score = db.latest_score(p.id)
        sr = pipeline.score_stored(db, p.id) if metrics else None
        units = [float(m.units) for m in metrics][-35:]
        rows.append((score.total if score else -1, [
            f"<a href='/product?id={esc(p.id)}'>{esc(p.id)}</a>",
            esc(p.name), esc(p.category),
            f"${price:.2f}" if price else "—",
            f"{score.total:.0f}" if score else "—",
            chip(verdict(score.gates_passed, score.total)) if score else "—",
            stage_chip(sr.lifecycle.stage) if sr else "—",
            sparkline(units, width=120, height=28) if len(units) >= 2 else "—",
        ]))
    rows.sort(key=lambda r: r[0], reverse=True)

    body.append(f"<h2>{len(rows)} result(s)</h2><div class=panel>")
    if rows:
        body.append(table(["Product", "Name", "Category", "Price", "Score", "Verdict",
                           "Lifecycle", "Trend"], [r for _, r in rows], num_cols={3, 4}))
    else:
        body.append("<p class=mut>Nothing matches — loosen the filters or import more "
                    "data (<code>import-csv</code>).</p>")
    body.append("</div>")
    return page("Search", "".join(body), "/search")


_SUGGESTED_QUESTIONS = [
    "What should I do next?",
    "Which product should I test first and why?",
    "What's my true profit after all fees?",
    "Where do I source with fast shipping?",
    "When do I kill a test?",
    "How do I find products that will sell?",
]


def page_assistant(db: Database, q: dict) -> str:
    from ..assistant import answer as assistant_answer

    question = (q.get("q") or [""])[0].strip()
    body = ["<h1>Assistant</h1>",
            "<blockquote>Ask about YOUR live state (board, verdicts, next actions, "
            "playbook) or how anything in the engine works. It answers from your real "
            "data + the engine's knowledge — it never invents numbers, and it never "
            "executes anything: every action it suggests is a command you run."
            "</blockquote>",
            "<div class=panel><form class=calc method=get action=/assistant>"
            f"<label style='flex:1;min-width:320px'>Question"
            f"<input name=q value='{esc(question)}' style='width:100%'></label>"
            "<button>Ask</button></form>",
            "<p class=mut>Try: "
            + " · ".join(f"<a href='/assistant?q={esc(s.replace(' ', '+'))}'>{esc(s)}</a>"
                         for s in _SUGGESTED_QUESTIONS)
            + "</p></div>"]

    if question:
        result = assistant_answer(db, question)
        mode = ("<span class='chip TEST'>LLM</span>" if result.mode == "llm"
                else "<span class='chip info'>offline routing</span>")
        body.append(f"<h2>Answer {mode}</h2>"
                    f"<div class=panel>{md_to_html(result.text)}</div>")
        if result.mode == "offline":
            body.append("<p class=mut>Set <code>ANTHROPIC_API_KEY</code> in "
                        "<code>.env</code> for conversational answers grounded in the "
                        "same data.</p>")
    return page("Assistant", "".join(body), "/assistant")


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
                elif url.path == "/launch":
                    html = page_launch(db)
                elif url.path == "/playbook":
                    html = page_playbook(db)
                elif url.path == "/playbook/toggle":
                    step_id = (q.get("id") or [""])[0]
                    done = (q.get("done") or ["1"])[0] == "1"
                    playbook_toggle(db, step_id, done)  # unknown/auto ids are a silent no-op
                    return self._redirect("/playbook")
                elif url.path == "/autopilot/run":
                    from .. import autopilot
                    autopilot.run(db)               # propose + policy-auto only; no spend
                    return self._redirect("/")
                elif url.path == "/autopilot/approve":
                    from .. import autopilot
                    aid = (q.get("id") or ["0"])[0]
                    item = db.autopilot_action(int(aid)) if aid.isdigit() else None
                    # Browser approval is for INTERNAL steps and product-selection
                    # DECISIONS (both are free) — anything that spends money stays a
                    # deliberate CLI step (design invariant: dashboard never spends).
                    if (item and item["kind"] in ("internal", "decision")
                            and item["status"] == "pending"):
                        try:
                            autopilot.approve(db, item["id"])
                        except ValueError:
                            pass
                    return self._redirect("/")
                elif url.path == "/autopilot/reject":
                    from .. import autopilot
                    aid = (q.get("id") or ["0"])[0]
                    if aid.isdigit():
                        try:
                            autopilot.reject(db, int(aid))
                        except ValueError:
                            pass
                    return self._redirect("/")
                elif url.path == "/advertising":
                    html = page_advertising(db)
                elif url.path == "/shot-mode":
                    from ..creative.realism import SHOT_MODES
                    m = (q.get("set") or [""])[0]
                    if m in SHOT_MODES:
                        db.set_setting("shot_mode", m)     # free toggle, no spend
                    return self._redirect("/advertising")
                elif url.path == "/publish":
                    html = page_publish(db, (q.get("id") or [""])[0],
                                        (q.get("confirm") or [""])[0] == "1")
                elif url.path == "/actors":
                    html = page_actors(db, (q.get("use") or [""])[0])
                elif url.path == "/actors/new":
                    from ..creative import create_spec
                    actor = (q.get("actor") or [""])[0]
                    prod = (q.get("product") or [""])[0]
                    sid = create_spec(db, prod, actor_slug=actor)
                    if sid is None:
                        return self._redirect("/actors")
                    return self._redirect(f"/product?id={prod}")
                elif url.path == "/actors/variants":
                    from ..creative import create_variants
                    prod = (q.get("product") or [""])[0]
                    create_variants(db, prod)          # one spec per roster actor
                    return self._redirect(f"/product?id={prod}" if prod else "/actors")
                elif url.path == "/ideas":
                    html = page_ideas(db)
                elif url.path == "/organic":
                    html = page_organic(db)
                elif url.path == "/styles":
                    html = page_styles(db)
                elif url.path == "/budget":
                    html = page_budget(db, q)
                elif url.path == "/creators":
                    html = page_creators(db)
                elif url.path == "/million":
                    html = page_million(db, q)
                elif url.path == "/search":
                    html = page_search(db, q)
                elif url.path == "/assistant":
                    html = page_assistant(db, q)
                else:
                    return self._send(404, page("Not found", "<h1>404</h1>"))
            self._send(200, html)
        except Exception as e:  # show the error instead of a hung tab (local tool)
            self._send(500, page("Error", f"<h1>Error</h1><pre>{esc(repr(e))}</pre>"))

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

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
