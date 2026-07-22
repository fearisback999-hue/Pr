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
            if i["kind"] == "internal":
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
                    "— the same ranking `packet` uses).</p></div>")

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
                    # Browser approval is for INTERNAL steps only — anything that
                    # spends money stays a deliberate CLI step (design invariant:
                    # the dashboard never spends money).
                    if item and item["kind"] == "internal" and item["status"] == "pending":
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
