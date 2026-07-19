"""Command-line entry points. Run each stage by hand before trusting the cron — the iron
rule of automation (Part 0): never automate anything you have not run manually first.

New to this? Start here:
    python -m tt_engine.cli playbook          # the whole business, zero to hero, in order
    python -m tt_engine.cli serve              # the dashboard — everything on one site

Data in (Phase 1 — manual first, no scrapers):
    python -m tt_engine.cli add --name "..." --category beauty --price 24.99
    python -m tt_engine.cli add-supplier <product_id> --cost 6.50 --ship-cost 1.20
    python -m tt_engine.cli add-metric <product_id> --units 120 --price 24.99 [...]
    python -m tt_engine.cli import-csv <file.csv> --source kalodata|fastmoss|generic
    python -m tt_engine.cli seed [--demo-outcomes]          # offline sample data

Detect / score / decide:
    python -m tt_engine.cli find [--top 5]      # ← the best winning products, ranked
    python -m tt_engine.cli daily
    python -m tt_engine.cli scorecard <product_id> [--out FILE.md]   # KILL/WATCH/TEST
    python -m tt_engine.cli board · score <id> · packet <id> · export

Live tests (kill/scale tracker):
    python -m tt_engine.cli log-test <product_id> --spend 40 --revenue 40 [--date ...]
    python -m tt_engine.cli validate <product_id>            # 48h kill timer included
    python -m tt_engine.cli log-result <product_id> --decision kill|scale

Phase 2 (psychology + creative + feedback):
    python -m tt_engine.cli psych <product_id> [--file comments.txt]
    python -m tt_engine.cli creative <product_id> [--confirm] [--variations 30]
    python -m tt_engine.cli export-creatives <product_id> [--out FILE.json]
    python -m tt_engine.cli report-monthly [--month YYYY-MM] [--out FILE.md]
    python -m tt_engine.cli recalibrate [--apply]

Ops:
    python -m tt_engine.cli weekly [--out reports/out] · plan
    python -m tt_engine.cli capital --capital 5000 · health --ship-days 4 --refund-rate 0.03
"""

from __future__ import annotations

import argparse
import sys

from . import pipeline
from . import seed as seedmod
from .config import CONFIG
from .db import Database
from .feedback import recalibrate
from .llm import LLMClient
from .reports.opportunity import render_board, render_report
from .scoring import load_weights
from .validation import WEEK_PLAN, decide, summarize_tests


def _db(args) -> Database:
    return Database(args.db)


def cmd_seed(args) -> int:
    with _db(args) as db:
        n = seedmod.seed_sample(db)
        print(f"seeded {n} sample products + suppliers into {db.path}")
        if args.demo_outcomes:
            m = seedmod.seed_demo_outcomes(db)
            print(f"seeded {m} synthetic scored products + labeled results for Part-13 recalibration")
    return 0


def cmd_daily(args) -> int:
    with _db(args) as db:
        result = pipeline.daily(db)
        print(f"[daily {result.date}] {result.headline}\n")
        for sr in result.scored:
            s = sr.breakdown.score
            tag = "ATTACK" if (s.gates_passed and s.total >= CONFIG.score_threshold) else (
                "watch" if s.gates_passed else "GATED")
            print(f"  {s.total:5.0f}  {s.product_id:<20} [{tag:<6}] {sr.trigger.headline}")
            if not s.gates_passed:
                print(f"         ⛔ {', '.join(s.gate_failures)}")
        print(f"\nNew attack-ready candidates: "
              f"{', '.join(c.record.product.id for c in result.new_candidates) or '(none)'}")
    return 0


def cmd_weekly(args) -> int:
    llm = LLMClient()
    if not llm.available:
        print("(LLM not configured — psychology/hooks/scripts use the deterministic offline fallback)\n")
    with _db(args) as db:
        report = pipeline.weekly(db, out_dir=args.out, llm=llm, push_creative=not args.no_creative)
        if args.out:
            print(f"wrote report + briefs to {args.out}/\n")
        print(render_report(report))
    return 0


def cmd_find(args) -> int:
    """The core job: find the best winning products to move on right now, ranked."""
    from .reports.opportunity import render_winners
    llm = LLMClient()
    if not llm.available:
        print("(LLM not configured — psychology uses the deterministic offline fallback)\n")
    with _db(args) as db:
        result = pipeline.find_winners(db, top=args.top, llm=llm)
        print(render_winners(result.winners, result.near_misses, result.source, result.date))
    return 0


def cmd_board(args) -> int:
    with _db(args) as db:
        scores = db.board()
        if not scores:
            print("no scores yet — run `seed` then `daily`")
            return 1
        print(render_board(scores))
    return 0


def cmd_score(args) -> int:
    with _db(args) as db:
        sr = pipeline.score_stored(db, args.product_id)
        if sr is None:
            print(f"no stored metrics for {args.product_id} — run `seed`/`daily` first")
            return 1
        b = sr.breakdown
        s = b.score
        print(f"# {sr.record.product.name}  ({s.product_id})")
        print(f"TOTAL {s.total:.1f}/100 · ~{s.window_days:.0f}d runway · "
              f"gates {'PASS' if s.gates_passed else 'FAIL'}")
        if not s.gates_passed:
            print(f"  ⛔ {', '.join(s.gate_failures)}")
        print(f"\n{sr.trigger.momentum.summary}\n{sr.trigger.saturation.summary}\n")
        print(f"economics: {sr.economics.summary}\n")
        for cat, pts in b.category_points.items():
            w = b.weights.get(cat, 0)
            print(f"  {cat.replace('_', ' '):<20} {pts:5.1f}/{w:>2.0f}")
            for comp, cp in b.components[cat].items():
                print(f"      {comp:<22} {cp:5.2f}")
    return 0


def cmd_packet(args) -> int:
    """Build a full attack packet (uses the live feed so reviews flow into psychology)."""
    llm = LLMClient()
    with _db(args) as db:
        result = pipeline.daily(db)
        match = next((s for s in result.scored if s.record.product.id == args.product_id), None)
        if match is None:
            print(f"{args.product_id} not found in the current feed")
            return 1
        packet = pipeline.build_attack_packet(db, match, llm, push_creative=not args.no_creative)
        print(packet.render())
    return 0


def cmd_validate(args) -> int:
    from .validation import hours_below_breakeven
    with _db(args) as db:
        product = db.get_product(args.product_id)
        if product is None:
            print(f"{args.product_id} not found")
            return 1
        tests = db.tests_for_product(args.product_id)
        if not tests:
            print(f"No test telemetry for {args.product_id} yet. The 30-day plan:\n")
            for week, plan in WEEK_PLAN.items():
                print(f"  Week {week}: {plan}")
            return 0
        summary = summarize_tests(args.product_id, tests)
        sr = pipeline.score_stored(db, args.product_id)
        breakeven = sr.economics.breakeven_roas if sr else float("inf")
        result = db.latest_result(args.product_id)
        refund = result.refund_rate if result else None
        decision = decide(summary, breakeven, refund_rate=refund, tests=tests)
        print(decision.headline)
        hours, detail = hours_below_breakeven(tests, breakeven)
        print(f"\n  spend ${summary.spend:.0f} · CTR "
              f"{(summary.avg_ctr or 0)*100:.2f}% · ROAS {summary.avg_roas or 0:.2f} "
              f"(break-even {breakeven:.2f}) · winner: {summary.has_clear_winner}")
        print(f"  48h timer: {detail}")
    return 0


def cmd_recalibrate(args) -> int:
    with _db(args) as db:
        result = recalibrate(db, apply=args.apply)
        print(result.summary)
        # Only nudge toward --apply when a fit actually happened (weights moved).
        if not args.apply and result.correlations:
            print("\n(dry run — re-run with --apply to write weights.json)")
    return 0


def cmd_plan(args) -> int:
    print("30-Day Validation Framework (Part 9):\n")
    for week, plan in WEEK_PLAN.items():
        print(f"  Week {week}: {plan}")
    print("\nWeights in use (Part 3 / recalibrated by Part 13):")
    for cat, w in load_weights().items():
        print(f"  {cat:<20} {w:>5.1f}")
    print("\nReminder (Part 12 builder's trap): the engine is the asset. Run the store.")
    return 0


def cmd_export(args) -> int:
    from .reports.spreadsheet import export_csv
    with _db(args) as db:
        n = export_csv(db, args.out)
        if n == 0:
            print("no scored products with metrics — run `seed`/`daily` first")
            return 1
        print(f"wrote Appendix-A board ({n} rows) to {args.out}")
    return 0


def cmd_capital(args) -> int:
    from .capital import plan_capital
    plan = plan_capital(
        capital=args.capital, test_budget=args.test_budget,
        payout_lag_days=args.payout_lag, daily_ad_spend=args.daily_ad,
        daily_cogs=args.daily_cogs, monthly_fixed=args.monthly_fixed,
    )
    print("Capital & cash flow (Part 11) — tracking only; the spend decision stays human:\n")
    print(plan.summary)
    return 0


def cmd_health(args) -> int:
    from .account import assess_health
    health = assess_health(args.ship_days, args.refund_rate, args.response_hrs)
    print("Account health (Part 10) — a low Shop Performance Score throttles reach:\n")
    print(health.summary)
    return 0


# ── Phase 1: manual data entry + CSV import ─────────────────────────────────────
def cmd_add(args) -> int:
    from datetime import date as _date
    from .db import models
    from .feeds.csv_import import slug_id
    with _db(args) as db:
        pid = args.id or slug_id(args.name)
        db.upsert_product(models.Product(
            id=pid, name=args.name, category=args.category.lower(),
            first_seen=_date.today().isoformat(),
            branded=args.branded, restricted=args.restricted,
        ))
        print(f"added {pid}: {args.name} ({args.category})")
        if (args.price is None) != (args.units is None):
            print("  ⚠️  --price and --units go together — no metric logged; "
                  "use `add-metric` with both")
        if args.price is not None and args.units is not None:
            db.upsert_metric(models.DailyMetric(
                product_id=pid, date=args.date or _date.today().isoformat(),
                units=args.units, gmv=round(args.units * args.price, 2), price=args.price,
                sellers=args.sellers, promo_videos=args.promo_videos, ads=args.ads,
                avg_ad_age=args.avg_ad_age,
            ))
            print(f"  + first daily metric ({args.units} units @ ${args.price:.2f})")
        else:
            print("  next: `add-metric` daily so momentum has a series, and "
                  "`add-supplier` so economics can be scored (no landed cost = no score)")
    return 0


def cmd_add_supplier(args) -> int:
    from .db import models
    with _db(args) as db:
        if db.get_product(args.product_id) is None:
            print(f"{args.product_id} not found — `add` it first")
            return 1
        ref = args.ref or f"SUP-{args.product_id}"
        db.upsert_supplier(models.Supplier(
            ref=ref, product_id=args.product_id, name=args.name,
            cost=args.cost, ship_cost=args.ship_cost, ship_days=args.ship_days,
            moq=args.moq, us_warehouse=args.us_warehouse, rating=args.rating,
            response_hrs=args.response_hrs, quality_notes=args.notes,
        ))
        print(f"added supplier {ref}: ${args.cost:.2f} + ${args.ship_cost:.2f} ship "
              f"= ${args.cost + args.ship_cost:.2f} landed — economics can now be scored")
    return 0


def cmd_add_metric(args) -> int:
    from datetime import date as _date
    from .db import models
    with _db(args) as db:
        if db.get_product(args.product_id) is None:
            print(f"{args.product_id} not found — `add` it first")
            return 1
        gmv = args.gmv if args.gmv is not None else round(args.units * args.price, 2)
        db.upsert_metric(models.DailyMetric(
            product_id=args.product_id, date=args.date or _date.today().isoformat(),
            units=args.units, gmv=gmv, price=args.price, sellers=args.sellers,
            promo_videos=args.promo_videos, ads=args.ads, avg_ad_age=args.avg_ad_age,
        ))
        print(f"logged {args.units} units / ${gmv:.2f} GMV for {args.product_id}")
    return 0


def cmd_import_csv(args) -> int:
    from .feeds import import_csv
    overrides = {}
    for m in args.map or []:
        col, _, fieldname = m.partition("=")
        if not fieldname:
            print(f"bad --map '{m}' — expected \"CSV Column=field\"")
            return 1
        overrides[col] = fieldname
    with _db(args) as db:
        try:
            result = import_csv(db, args.file, source=args.source, column_map=overrides,
                                default_category=args.category)
        except FileNotFoundError:
            print(f"import failed: {args.file} not found")
            return 1
        except ValueError as e:
            print(f"import failed: {e}")
            return 1
        print(result.summary)
        print("\nnext: `daily` to detect+score, or `scorecard <id>` for one product")
    return 0


# ── Phase 1: scorecard + kill/scale tracker ─────────────────────────────────────
def cmd_scorecard(args) -> int:
    from .reports.scorecard import render_scorecard
    with _db(args) as db:
        sr = pipeline.score_stored(db, args.product_id)
        if sr is None:
            print(f"no stored metrics for {args.product_id} — add/import data first")
            return 1
        db.upsert_score(sr.breakdown.score)
        text = render_scorecard(sr)
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out}")
        else:
            print(text)
    return 0


def cmd_log_test(args) -> int:
    from datetime import date as _date
    from .db import models
    with _db(args) as db:
        if db.get_product(args.product_id) is None:
            print(f"{args.product_id} not found")
            return 1
        date = args.date or _date.today().isoformat()
        creative_id = args.creative
        if creative_id is None:
            # Manual tests hang off a per-product placeholder creative.
            creative_id = f"{args.product_id}-MANUAL"
            if not any(c.id == creative_id for c in db.creatives_for(args.product_id)):
                db.upsert_creative(models.Creative(
                    id=creative_id, product_id=args.product_id, format="Manual",
                    hook="manual ad test", status="ready",
                ))
        elif not any(c.id == creative_id for c in db.creatives_for(args.product_id)):
            print(f"creative '{creative_id}' not found on {args.product_id} — "
                  "omit --creative to log against the manual placeholder")
            return 1
        roas = (args.revenue / args.spend) if args.spend > 0 else 0.0
        db.upsert_test(models.Test(
            id=f"{creative_id}-{date}", creative_id=creative_id, date=date,
            spend=args.spend, impressions=args.impressions,
            three_sec_vr=args.three_sec_vr, ctr=args.ctr, atc=args.atc,
            cvr=args.cvr, roas=round(roas, 3),
        ))
        print(f"logged {date}: ${args.spend:.2f} spend, ${args.revenue:.2f} revenue "
              f"→ ROAS {roas:.2f}")
        print("run `validate` to check the kill/scale call (48h timer included)")
    return 0


def cmd_log_result(args) -> int:
    from datetime import date as _date
    from .db import models
    with _db(args) as db:
        if db.get_product(args.product_id) is None:
            print(f"{args.product_id} not found")
            return 1
        db.upsert_result(models.Result(
            product_id=args.product_id, date=args.date or _date.today().isoformat(),
            net_margin=args.net_margin, refund_rate=args.refund_rate,
            roas=args.roas, decision=args.decision,
        ))
        print(f"recorded {args.decision.upper()} for {args.product_id} — this feeds the "
              "monthly recalibration report (`report-monthly`)")
    return 0


# ── Phase 2: psychology, creative pipeline, feedback ────────────────────────────
def cmd_psych(args) -> int:
    from .psychology import analyze
    with _db(args) as db:
        product = db.get_product(args.product_id)
        if product is None:
            print(f"{args.product_id} not found")
            return 1
        new: list[str] = []
        if args.file:
            from pathlib import Path
            try:
                new = [ln.strip() for ln in Path(args.file).read_text().splitlines()
                       if ln.strip()]
            except FileNotFoundError:
                print(f"{args.file} not found")
                return 1
        if new:
            product.reviews = product.reviews + [r for r in new if r not in product.reviews]
            db.upsert_product(product)
            print(f"added {len(new)} comment(s) — corpus now {len(product.reviews)}\n")
        if not product.reviews:
            print("no reviews/comments on file — paste top comments into a text file "
                  "(one per line) and re-run with --file")
            return 1
        llm = LLMClient()
        p = analyze(product.name, product.reviews, product.category, llm)
        print(f"source: {p.source}"
              + ("" if p.source == "llm" else " (set ANTHROPIC_API_KEY for the LLM pass)"))
        print(f"\nemotional trigger : {p.emotional_trigger}")
        print(f"pain point        : {p.pain_point}")
        print(f"desire            : {p.desire}")
        print(f"identity appeal   : {p.identity_appeal}")
        print(f"impulse factor    : {p.impulse_factor}")
        print(f"\n— the paragraph that feeds the creative brief —\n{p.spine}")
    return 0


def cmd_creative(args) -> int:
    from .creative import ConfirmationRequired
    with _db(args) as db:
        try:
            kit, result = pipeline.produce_creatives(
                db, args.product_id, confirm=args.confirm,
                variations=args.variations, force=args.force,
            )
        except (ValueError, ConfirmationRequired) as e:
            print(f"refused: {e}")
            return 1
        print(result.summary)
        if args.brief:
            from pathlib import Path
            Path(args.brief).parent.mkdir(parents=True, exist_ok=True)
            Path(args.brief).write_text(kit.brief_text())
            print(f"brief written to {args.brief}")
    return 0


def cmd_export_creatives(args) -> int:
    from .creative import export_creatives
    with _db(args) as db:
        result = export_creatives(db, args.product_id, args.out)
        print(result.summary)
        return 1 if result.blocked else 0


def cmd_report_monthly(args) -> int:
    from .feedback import render_monthly
    with _db(args) as db:
        text = render_monthly(db, month=args.month)
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out}")
        else:
            print(text)
    return 0


# ── dashboard + guide + POD planner ─────────────────────────────────────────────
def cmd_serve(args) -> int:
    from .web import run
    run(args.db, host=args.host, port=args.port)
    return 0


def cmd_next(args) -> int:
    from .guide import render_guide
    with _db(args) as db:
        print(render_guide(db, limit=args.limit))
    return 0


def cmd_pod(args) -> int:
    from .capital import plan_pod
    try:
        plan = plan_pod(
            target_monthly_profit=args.target, profit_per_sale=args.profit,
            sales_per_listing_month=args.sales_per_listing,
            current_listings=args.current, hours_per_week=args.hours,
            minutes_per_listing=args.minutes,
        )
    except ValueError as e:
        print(f"error: {e}")
        return 1
    print("Etsy POD listing plan (all assumptions are flags — see --help):\n")
    print(plan.summary)
    return 0


def _scored_or_fail(db, product_id):
    sr = pipeline.score_stored(db, product_id)
    if sr is None:
        print(f"no stored metrics for {product_id} — add/import data first")
    return sr


def cmd_analyze(args) -> int:
    from .analysis import analyze_market
    from .psychology import analyze
    llm = LLMClient()
    with _db(args) as db:
        sr = _scored_or_fail(db, args.product_id)
        if sr is None:
            return 1
        product = sr.record.product
        psych = analyze(product.name, product.reviews, product.category, llm)
        text = analyze_market(sr, psych).render()
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out}")
        else:
            print(text)
    return 0


def cmd_creative_pack(args) -> int:
    from .creative import build_pack
    from .psychology import analyze
    llm = LLMClient()
    with _db(args) as db:
        product = db.get_product(args.product_id)
        if product is None:
            print(f"{args.product_id} not found")
            return 1
        psych = analyze(product.name, product.reviews, product.category, llm)
        pack = build_pack(product, psych, llm=llm)
        text = pack.render()
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out} — {len(pack.hooks)} hooks, {len(pack.concepts)} "
                  f"concepts, {len(pack.paid_scripts)}+{len(pack.organic_scripts)} scripts"
                  + (f", ⚠️ {len(pack.flagged)} compliance flag(s)" if pack.flagged else ""))
        else:
            print(text)
    return 0


def cmd_production(args) -> int:
    """The step-by-step production runbook: actor image → per-scene first-frames →
    Seedance animate → ElevenLabs voice → CapCut assembly (keyframe-first pipeline)."""
    from .creative import build_pack, build_runbook
    from .psychology import analyze
    llm = LLMClient()
    with _db(args) as db:
        product = db.get_product(args.product_id)
        if product is None:
            print(f"{args.product_id} not found")
            return 1
        psych = analyze(product.name, product.reviews, product.category, llm)
        pack = build_pack(product, psych, llm=llm)
        runbook = build_runbook(product, pack, n_ads=args.ads)
        text = runbook.render()
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out} — {len(runbook.ads)} ad(s), "
                  f"{sum(len(a.scenes) for a in runbook.ads)} scenes")
        else:
            print(text)
    return 0


def cmd_landing(args) -> int:
    from .psychology import analyze
    from .reports.landing import build_landing_page
    llm = LLMClient()
    with _db(args) as db:
        sr = _scored_or_fail(db, args.product_id)
        if sr is None:
            return 1
        product = sr.record.product
        psych = analyze(product.name, product.reviews, product.category, llm)
        suppliers = db.suppliers_for(product.id)
        us_wh = any(s.us_warehouse for s in suppliers)
        page = build_landing_page(product, psych, sr.economics, us_warehouse=us_wh)
        text = page.render()
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out}"
                  + (f" — ⚠️ {len(page.flagged)} compliance flag(s)" if page.flagged else ""))
        else:
            print(text)
    return 0


def cmd_search(args) -> int:
    from .reports.scorecard import verdict
    with _db(args) as db:
        q = (args.q or "").lower()
        rows = []
        for p in db.all_products():
            if q and q not in p.name.lower() and q not in p.id.lower():
                continue
            if args.category and p.category.lower() != args.category.lower():
                continue
            metrics = db.metrics_for(p.id)
            price = metrics[-1].price if metrics else None
            if args.min_price is not None and (price is None or price < args.min_price):
                continue
            if args.max_price is not None and (price is None or price > args.max_price):
                continue
            score = db.latest_score(p.id)
            rows.append((p, price, score))
        if not rows:
            print("no products match")
            return 1
        rows.sort(key=lambda r: (r[2].total if r[2] else -1), reverse=True)
        for p, price, score in rows:
            v = verdict(score.gates_passed, score.total) if score else "—"
            total = f"{score.total:.0f}" if score else "—"
            pr = f"${price:.2f}" if price else "—"
            print(f"{total:>4}  [{v:<5}] {p.id:<20} {pr:>8}  {p.category:<12} {p.name}")
    return 0


def cmd_month_one(args) -> int:
    from .capital import plan_month_one
    try:
        plan = plan_month_one(
            tests=args.tests, test_budget=args.test_budget,
            samples=args.samples, sample_cost=args.sample_cost,
            data_sub=args.data_sub, formation=args.formation,
            winner_prob=args.winner_prob, true_margin=args.margin,
        )
    except ValueError as e:
        print(f"error: {e}")
        return 1
    print("Month one: initial cash + expected profit (all knobs are flags — see --help)\n")
    print(plan.summary)
    return 0


def cmd_ask(args) -> int:
    from .assistant import answer
    with _db(args) as db:
        result = answer(db, args.question)
        print(f"[{result.mode}]")
        print(result.text)
    return 0


def cmd_optimize(args) -> int:
    from .economics import optimize_offer
    with _db(args) as db:
        product = db.get_product(args.product_id)
        if product is None:
            print(f"{args.product_id} not found")
            return 1
        suppliers = db.suppliers_for(args.product_id)
        if not suppliers:
            print("no real landed cost on file — the optimizer refuses to run on guesses "
                  f"(add one: add-supplier {args.product_id} --cost X --ship-cost Y)")
            return 1
        best = min(suppliers, key=lambda s: s.cost + s.ship_cost)
        metrics = db.metrics_for(args.product_id)
        if not metrics:
            print("no metrics — no price on record to optimize around")
            return 1
        from .pipeline import return_rate_for
        report = optimize_offer(
            args.product_id, sell_price=metrics[-1].price,
            supplier_cost=best.cost, ship_cost=best.ship_cost,
            payment_rate=args.payment, affiliate_rate=args.affiliate,
            return_rate=return_rate_for(product.category, product.reviews),
            tests=db.tests_for_product(args.product_id),
        )
        text = report.render()
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out}")
        else:
            print(text)
    return 0


def cmd_select(args) -> int:
    """The test queue, ranked by expected dollars: EV = p(win)·payoff − p(lose)·loss
    at the TRUE fee stack. Ineligible products (gates / threshold / unpriced) are
    listed with their blocker — the refusal is information, not an error."""
    from .selection import rank_for_test
    with _db(args) as db:
        products = db.all_products()
        scored = [sr for sr in (pipeline.score_stored(db, p.id) for p in products) if sr]
        if not scored:
            print("no stored metrics — run `seed`/`daily`/`import-csv` first")
            return 1
        ranked = rank_for_test(scored)
        print("# Test queue — ranked by expected value (not by score)\n")
        for sr in ranked:
            sel, s = sr.selection, sr.breakdown.score
            print(f"{s.product_id}  ·  score {s.total:.0f}  ·  {sr.record.product.name}")
            print(f"   {sel.ev.summary}")
            print(f"   {sel.ceiling.summary}")
            for note in sel.ceiling.notes:
                print(f"   ⚠ {note}")
            print()
        print("EV is a prior for ORDERING the queue — the 48h kill timer decides "
              "what happens after money moves. `scale` shows what these must stack to.")
    return 0


def cmd_ai_plan(args) -> int:
    """The persona's advertising plan for one product: fit (what it may/may never
    carry), cadence, the Spark loop, and the lane economics."""
    from .creative import build_creator_plan
    with _db(args) as db:
        sr = pipeline.score_stored(db, args.product_id)
        if sr is None:
            print(f"no stored metrics for {args.product_id} — import or add data first")
            return 1
        plan = build_creator_plan(sr.record.product, sr.economics,
                                  reviews=sr.record.reviews)
        print(plan.render())
    return 0


def cmd_autopilot(args) -> int:
    """The approval-gated automation loop: run proposes, you approve, it executes."""
    from . import autopilot
    with _db(args) as db:
        try:
            if args.ap_action == "run":
                report = autopilot.run(db)
                print(report.headline + "\n")
                print(autopilot.render_queue(db))
            elif args.ap_action == "queue":
                print(autopilot.render_queue(db))
            elif args.ap_action in ("approve", "reject"):
                if args.target is None or not args.target.isdigit():
                    print(f"usage: autopilot {args.ap_action} <queue-item-id>")
                    return 1
                aid = int(args.target)
                if args.ap_action == "approve":
                    print(f"✓ executed: {autopilot.approve(db, aid)}")
                else:
                    autopilot.reject(db, aid, args.why or "")
                    print(f"✗ rejected #{aid}")
            elif args.ap_action == "policy":
                if not args.target:
                    from .autopilot import EXTERNAL_STAGES, INTERNAL_STAGES
                    policy = db.autopilot_policy()
                    for s in INTERNAL_STAGES:
                        print(f"  {s:<16} {policy.get(s, 'approve')}")
                    for s in EXTERNAL_STAGES:
                        print(f"  {s:<16} approve (locked — spends money)")
                else:
                    print(autopilot.set_policy(db, args.target, args.mode or "approve"))
        except ValueError as e:
            print(f"error: {e}")
            return 1
    return 0


def cmd_persona(args) -> int:
    """Show the parsed creator bible + production-readiness warnings."""
    from .creative.persona import load_persona, validate_persona
    p = load_persona(args.path)
    warnings = validate_persona(p)
    if p is None:
        print(warnings[0])
        return 1
    print(f"# Creator bible — parsed OK from {p.source_path}\n")
    print(p.summary + "\n")
    print("CASTING BLOCK (opens every prompt, verbatim):")
    print(f"  {p.casting_spec(soul_id='<HIGGSFIELD_SOUL_ID>')}\n")
    print("OUTFITS (one per product batch, itemized, repeated exactly):")
    for slot, outfit in sorted(p.outfits.items()):
        print(f"  {slot}: {outfit}")
    print(f"\nSETTINGS (her rooms — prompts never leave them): {', '.join(p.settings)}")
    print(f"SPEECH QUIRKS: {'; '.join(p.speech_quirks)}")
    if p.voice_reference:
        print(f"VOICE REF (pin it, feed it to every native-audio gen): {p.voice_reference}")
    if warnings:
        print("\n⚠ Not production-ready yet:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("\n✓ Production-ready. Train the Soul ID from the bible's photo "
              "checklist, then set HIGGSFIELD_SOUL_ID.")
    return 0


def cmd_scale(args) -> int:
    from .roadmap import plan_scale
    try:
        plan = plan_scale(monthly_revenue=args.revenue, aov=args.aov,
                          net_margin=args.margin, cogs_share=args.cogs)
    except ValueError as e:
        print(f"error: {e}")
        return 1
    print(plan.render())
    return 0


def cmd_roadmap(args) -> int:
    from .roadmap import plan_million, render_roadmap
    try:
        plan = plan_million(
            goal_amount=args.goal, goal_type=args.type, horizon_months=args.months,
            aov=args.aov, net_margin=args.margin, pod_listings=args.pod_listings,
        )
    except ValueError as e:
        print(f"error: {e}")
        return 1
    print(render_roadmap(plan))
    return 0


def cmd_playbook(args) -> int:
    from .playbook import render_playbook
    with _db(args) as db:
        text = render_playbook(db)
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text)
            print(f"wrote {args.out}")
        else:
            print(text)
    return 0


def _playbook_ids() -> list[str]:
    from .playbook import STEPS
    return [s.id for s in STEPS]


def cmd_playbook_check(args) -> int:
    ids = _playbook_ids()
    if args.step_id not in ids:
        print(f"unknown step '{args.step_id}'. Run `playbook` to see valid step ids.")
        return 1
    with _db(args) as db:
        db.set_playbook_step(args.step_id, True, note=args.note or "")
        print(f"checked off: {args.step_id}")
    return 0


def cmd_playbook_uncheck(args) -> int:
    ids = _playbook_ids()
    if args.step_id not in ids:
        print(f"unknown step '{args.step_id}'. Run `playbook` to see valid step ids.")
        return 1
    with _db(args) as db:
        db.set_playbook_step(args.step_id, False)
        print(f"unchecked: {args.step_id}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tt-engine", description=__doc__)
    parser.add_argument("--db", default=CONFIG.db_path, help="SQLite path (default: TT_DB_PATH)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("seed", help="seed sample products + suppliers")
    p.add_argument("--demo-outcomes", action="store_true",
                   help="also seed synthetic outcomes for the recalibration demo")
    p.set_defaults(func=cmd_seed)

    sub.add_parser("daily", help="run the daily detection + scoring pass").set_defaults(func=cmd_daily)

    p = sub.add_parser("find", help="find the best winning products to move on now (ranked)")
    p.add_argument("--top", type=int, default=5, help="how many winners to surface")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("weekly", help="build the weekly opportunity report + attack packets")
    p.add_argument("--out", default=None, help="directory to write report + briefs")
    p.add_argument("--no-creative", action="store_true", help="skip Higgsfield kit planning")
    p.set_defaults(func=cmd_weekly)

    sub.add_parser("board", help="show the ranked score board").set_defaults(func=cmd_board)

    p = sub.add_parser("score", help="detailed score breakdown for one product")
    p.add_argument("product_id")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("packet", help="full attack packet for one product")
    p.add_argument("product_id")
    p.add_argument("--no-creative", action="store_true")
    p.set_defaults(func=cmd_packet)

    p = sub.add_parser("validate", help="kill/scale decision from test telemetry (or the 30-day plan)")
    p.add_argument("product_id")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("recalibrate", help="recalibrate Part-3 weights from your outcomes (Part 13)")
    p.add_argument("--apply", action="store_true", help="write the new weights to weights.json")
    p.set_defaults(func=cmd_recalibrate)

    sub.add_parser("plan", help="show the 30-day framework + current weights").set_defaults(func=cmd_plan)

    p = sub.add_parser("export", help="export the Appendix-A scoring spreadsheet to CSV")
    p.add_argument("--out", default="reports/out/board.csv", help="CSV output path")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("capital", help="capital & cash-flow tracking (Part 11)")
    p.add_argument("--capital", type=float, required=True, help="starting capital ($)")
    p.add_argument("--test-budget", type=float, default=300.0, help="cost to test one product ($)")
    p.add_argument("--payout-lag", type=float, default=14.0, help="TikTok payout hold (days)")
    p.add_argument("--daily-ad", type=float, default=0.0, help="avg daily ad spend ($)")
    p.add_argument("--daily-cogs", type=float, default=0.0, help="avg daily COGS fronted ($)")
    p.add_argument("--monthly-fixed", type=float, default=0.0, help="monthly fixed costs ($)")
    p.set_defaults(func=cmd_capital)

    p = sub.add_parser("health", help="account health / Shop Performance proxy (Part 10)")
    p.add_argument("--ship-days", type=float, required=True, help="avg delivery time (days)")
    p.add_argument("--refund-rate", type=float, required=True, help="refund rate (0..1)")
    p.add_argument("--response-hrs", type=float, default=12.0, help="avg service response (hours)")
    p.set_defaults(func=cmd_health)

    # ── Phase 1: manual entry + CSV import ─────────────────────────────────────
    p = sub.add_parser("add", help="manually add a product found by hand")
    p.add_argument("--name", required=True)
    p.add_argument("--category", required=True, help="beauty|wellness|apparel|toys|electronics|home|…")
    p.add_argument("--id", default=None, help="product id (default: slug of the name)")
    p.add_argument("--branded", action="store_true", help="trademarked/licensed (hard gate)")
    p.add_argument("--restricted", action="store_true", help="restricted TikTok category (hard gate)")
    p.add_argument("--price", type=float, default=None, help="sell price (with --units logs day 1)")
    p.add_argument("--units", type=int, default=None, help="units/day observed (with --price)")
    p.add_argument("--date", default=None, help="metric date YYYY-MM-DD (default today)")
    p.add_argument("--sellers", type=int, default=0)
    p.add_argument("--promo-videos", type=int, default=0)
    p.add_argument("--ads", type=int, default=0)
    p.add_argument("--avg-ad-age", type=float, default=0.0)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("add-supplier", help="add a real landed-cost quote (required to score economics)")
    p.add_argument("product_id")
    p.add_argument("--cost", type=float, required=True, help="quoted unit cost ($)")
    p.add_argument("--ship-cost", type=float, default=0.0, help="per-unit shipping ($)")
    p.add_argument("--ship-days", type=float, default=7.0)
    p.add_argument("--ref", default=None, help="supplier ref (default SUP-<product>)")
    p.add_argument("--name", default="")
    p.add_argument("--moq", type=int, default=1)
    p.add_argument("--us-warehouse", action="store_true")
    p.add_argument("--rating", type=float, default=None)
    p.add_argument("--response-hrs", type=float, default=None)
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_add_supplier)

    p = sub.add_parser("add-metric", help="log one day of metrics for a hand-tracked product")
    p.add_argument("product_id")
    p.add_argument("--units", type=int, required=True)
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--gmv", type=float, default=None, help="default: units × price")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--sellers", type=int, default=0)
    p.add_argument("--promo-videos", type=int, default=0)
    p.add_argument("--ads", type=int, default=0)
    p.add_argument("--avg-ad-age", type=float, default=0.0)
    p.set_defaults(func=cmd_add_metric)

    p = sub.add_parser("import-csv", help="import a manually-exported Kalodata/FastMoss CSV")
    p.add_argument("file")
    p.add_argument("--source", default="generic", choices=["kalodata", "fastmoss", "generic"])
    p.add_argument("--map", action="append", metavar='"CSV Column=field"',
                   help="remap a column, e.g. --map \"Sales Volume=units\" (repeatable)")
    p.add_argument("--category", default="home", help="fallback category when the CSV has none")
    p.set_defaults(func=cmd_import_csv)

    # ── Phase 1: scorecard + kill/scale tracker ────────────────────────────────
    p = sub.add_parser("scorecard", help="markdown scorecard with KILL/WATCH/TEST verdict")
    p.add_argument("product_id")
    p.add_argument("--out", default=None, help="write to file instead of stdout")
    p.set_defaults(func=cmd_scorecard)

    p = sub.add_parser("log-test", help="log a day of live ad-test spend/revenue")
    p.add_argument("product_id")
    p.add_argument("--spend", type=float, required=True)
    p.add_argument("--revenue", type=float, required=True)
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--creative", default=None, help="creative id (default: manual placeholder)")
    p.add_argument("--impressions", type=int, default=0)
    p.add_argument("--three-sec-vr", type=float, default=None)
    p.add_argument("--ctr", type=float, default=None)
    p.add_argument("--atc", type=float, default=None)
    p.add_argument("--cvr", type=float, default=None)
    p.set_defaults(func=cmd_log_test)

    p = sub.add_parser("log-result", help="record a concluded test's outcome (feeds Part 13)")
    p.add_argument("product_id")
    p.add_argument("--decision", required=True, choices=["kill", "scale", "watch"])
    p.add_argument("--net-margin", type=float, default=None)
    p.add_argument("--refund-rate", type=float, default=None)
    p.add_argument("--roas", type=float, default=None)
    p.add_argument("--date", default=None)
    p.set_defaults(func=cmd_log_result)

    # ── Phase 2: psychology, creative, feedback ────────────────────────────────
    p = sub.add_parser("psych", help="psychology pass over pasted top comments/reviews")
    p.add_argument("product_id")
    p.add_argument("--file", default=None, help="text file of comments, one per line")
    p.set_defaults(func=cmd_psych)

    p = sub.add_parser("creative", help="Higgsfield batch for a TEST-verdict product (MCP)")
    p.add_argument("product_id")
    p.add_argument("--confirm", action="store_true",
                   help="actually generate (spends money); omit for the dry-run plan")
    p.add_argument("--variations", type=int, default=30)
    p.add_argument("--force", action="store_true", help="override the TEST-verdict gate")
    p.add_argument("--brief", default=None, help="also write the brief markdown here")
    p.set_defaults(func=cmd_creative)

    p = sub.add_parser("export-creatives", help="export manifest (blocks assets missing AIGC disclosure)")
    p.add_argument("product_id")
    p.add_argument("--out", default="reports/out/creatives.json")
    p.set_defaults(func=cmd_export_creatives)

    p = sub.add_parser("report-monthly", help="monthly recalibration report (suggestions only)")
    p.add_argument("--month", default=None, help="YYYY-MM (default: all outcomes)")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_report_monthly)

    # ── dashboard + guide + POD ────────────────────────────────────────────────
    p = sub.add_parser("serve", help="run the local dashboard (everything on one site)")
    p.add_argument("--host", default="127.0.0.1",
                   help="bind address (0.0.0.0 to reach it from other devices)")
    p.add_argument("--port", type=int, default=8787)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("next", help="what to do next, per product (most urgent first)")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("pod", help="Etsy print-on-demand: how many listings to publish")
    p.add_argument("--target", type=float, required=True, help="target profit $/month")
    p.add_argument("--profit", type=float, required=True,
                   help="profit per sale $ (price − POD base − ~9.5%% Etsy fees − ads)")
    p.add_argument("--sales-per-listing", type=float, default=0.3,
                   help="sales per listing per month (0.3 new shop; use YOUR measured rate)")
    p.add_argument("--current", type=int, default=0, help="listings live now")
    p.add_argument("--hours", type=float, default=5.0, help="hours/week you can spend")
    p.add_argument("--minutes", type=float, default=30.0, help="minutes per listing")
    p.set_defaults(func=cmd_pod)

    p = sub.add_parser("analyze", help="full market analysis: SWOT, risks, audience, offers")
    p.add_argument("product_id")
    p.add_argument("--out", default=None, help="write markdown to a file")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("creative-pack",
                       help="50 hooks + 50 UGC concepts + 20 paid/20 organic scripts + more")
    p.add_argument("product_id")
    p.add_argument("--out", default=None, help="write markdown to a file")
    p.set_defaults(func=cmd_creative_pack)

    p = sub.add_parser("production",
                       help="step-by-step video production runbook (keyframe-first "
                            "Seedance pipeline: actor → frames → animate → voice → assemble)")
    p.add_argument("product_id")
    p.add_argument("--ads", type=int, default=3, help="how many ad builds to detail")
    p.add_argument("--out", default=None, help="write markdown to a file")
    p.set_defaults(func=cmd_production)

    p = sub.add_parser("landing", help="landing-page copy (compliance-swept, honest slots)")
    p.add_argument("product_id")
    p.add_argument("--out", default=None, help="write markdown to a file")
    p.set_defaults(func=cmd_landing)

    p = sub.add_parser("search", help="search products by keyword / category / price")
    p.add_argument("--q", default=None, help="keyword in name or id")
    p.add_argument("--category", default=None)
    p.add_argument("--min-price", type=float, default=None)
    p.add_argument("--max-price", type=float, default=None)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("month-one",
                       help="initial cash needed + honest expected profit for month one")
    p.add_argument("--tests", type=int, default=2, help="ad tests this month (default 2)")
    p.add_argument("--test-budget", type=float, default=200.0, help="$ per test (150–300)")
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--sample-cost", type=float, default=18.0)
    p.add_argument("--data-sub", type=float, default=40.0, help="Kalodata-class sub $/mo")
    p.add_argument("--formation", type=float, default=0.0, help="LLC etc; sole-prop = 0")
    p.add_argument("--winner-prob", type=float, default=0.20, help="per-test hit rate")
    p.add_argument("--margin", type=float, default=0.50, help="true-stack contribution margin")
    p.set_defaults(func=cmd_month_one)

    p = sub.add_parser("ask", help="ask the assistant about your live state or the engine")
    p.add_argument("question")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("optimize",
                       help="profit optimizer: true fee stack + offer sweep + leak check")
    p.add_argument("product_id")
    p.add_argument("--affiliate", type=float, default=0.15,
                   help="affiliate commission you set (default 0.15; 0 for pure paid/organic)")
    p.add_argument("--payment", type=float, default=0.03,
                   help="payment-processing rate (research default 3%%; use your real rate)")
    p.add_argument("--out", default=None, help="write markdown to a file")
    p.set_defaults(func=cmd_optimize)

    p = sub.add_parser("select",
                       help="test queue ranked by expected dollars (EV), not points")
    p.set_defaults(func=cmd_select)

    p = sub.add_parser("ai-plan",
                       help="AI-persona advertising plan: fit, cadence, Spark loop, lanes")
    p.add_argument("product_id")
    p.set_defaults(func=cmd_ai_plan)

    p = sub.add_parser("autopilot",
                       help="approval-gated automation: propose → approve → execute")
    p.add_argument("ap_action", choices=("run", "queue", "approve", "reject", "policy"),
                   help="run = propose+refresh; approve/reject <id>; policy [stage mode]")
    p.add_argument("target", nargs="?", default=None,
                   help="queue item id (approve/reject) or stage name (policy)")
    p.add_argument("mode", nargs="?", default=None, choices=(None, "approve", "auto"))
    p.add_argument("--why", default="", help="reason for a rejection")
    p.set_defaults(func=cmd_autopilot)

    p = sub.add_parser("persona", help="parse + validate the creator bible (docs/persona/CREATOR.md)")
    p.add_argument("--path", default=None, help="override TT_PERSONA_PATH")
    p.set_defaults(func=cmd_persona)

    p = sub.add_parser("scale", help="the $100k month itemized: capital, portfolio, cadence")
    p.add_argument("--revenue", type=float, default=100_000.0,
                   help="target monthly revenue (default 100000)")
    p.add_argument("--aov", type=float, default=45.0)
    p.add_argument("--margin", type=float, default=0.16, help="blended net margin")
    p.add_argument("--cogs", type=float, default=0.35, help="COGS share of revenue")
    p.set_defaults(func=cmd_scale)

    p = sub.add_parser("roadmap", help="the honest milestone math from $0 to $1M")
    p.add_argument("--goal", type=float, default=1_000_000.0, help="target $ (default 1,000,000)")
    p.add_argument("--type", default="revenue", choices=["revenue", "profit"],
                   help="revenue (lifetime GMV, easier) or profit (take-home, top-1%% hard)")
    p.add_argument("--months", type=int, default=24, help="horizon in months (default 24)")
    p.add_argument("--aov", type=float, default=45.0, help="avg order value $ (TikTok ~$35–45)")
    p.add_argument("--margin", type=float, default=0.16,
                   help="net margin fraction (0.16 blended; ~0.35 organic-first)")
    p.add_argument("--pod-listings", type=int, default=0,
                   help="Etsy POD listings running in parallel (contributes ~$75/mo each)")
    p.set_defaults(func=cmd_roadmap)

    p = sub.add_parser("playbook",
                       help="the zero-to-hero checklist for the whole business, in order")
    p.add_argument("--out", default=None, help="write markdown to a file instead of stdout")
    p.set_defaults(func=cmd_playbook)

    p = sub.add_parser("playbook-check", help="check off a manual playbook step")
    p.add_argument("step_id")
    p.add_argument("--note", default="", help="optional note to attach")
    p.set_defaults(func=cmd_playbook_check)

    p = sub.add_parser("playbook-uncheck", help="uncheck a manual playbook step")
    p.add_argument("step_id")
    p.set_defaults(func=cmd_playbook_uncheck)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
