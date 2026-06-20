"""Command-line entry points. Run each stage by hand before trusting the cron — the iron
rule of automation (Part 0): never automate anything you have not run manually first.

    python -m tt_engine.cli seed [--demo-outcomes]
    python -m tt_engine.cli daily
    python -m tt_engine.cli weekly [--out reports/out] [--no-creative]
    python -m tt_engine.cli board
    python -m tt_engine.cli score <product_id>
    python -m tt_engine.cli packet <product_id>
    python -m tt_engine.cli validate <product_id>
    python -m tt_engine.cli recalibrate [--apply]
    python -m tt_engine.cli plan
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
        decision = decide(summary, breakeven, refund_rate=refund)
        print(decision.headline)
        print(f"\n  spend ${summary.spend:.0f} · CTR "
              f"{(summary.avg_ctr or 0)*100:.2f}% · ROAS {summary.avg_roas or 0:.2f} "
              f"(break-even {breakeven:.2f}) · winner: {summary.has_clear_winner}")
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tt-engine", description=__doc__)
    parser.add_argument("--db", default=CONFIG.db_path, help="SQLite path (default: TT_DB_PATH)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("seed", help="seed sample products + suppliers")
    p.add_argument("--demo-outcomes", action="store_true",
                   help="also seed synthetic outcomes for the recalibration demo")
    p.set_defaults(func=cmd_seed)

    sub.add_parser("daily", help="run the daily detection + scoring pass").set_defaults(func=cmd_daily)

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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
