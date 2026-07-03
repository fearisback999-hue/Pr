"""Command-line entry points. Run each stage by hand before trusting the cron — the iron
rule of automation (Part 0): never automate anything you have not run manually first.

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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
