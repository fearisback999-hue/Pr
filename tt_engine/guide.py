"""The operator guide: for every product, derive the single next action from what's
actually in the database — no memory required, no guessing. This is what "tell me what
to do on every step" means in practice: the engine reads its own state and hands you
the exact command.

Stage order (first unmet requirement wins):
  data → landed cost → score → verdict → psychology → creative → generate →
  export → launch → log daily → decide → record outcome
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Optional

from .config import CONFIG
from .db import Database, models
from .validation import KILL_HOURS, decide, hours_below_breakeven, summarize_tests


@dataclass
class Step:
    product_id: str
    name: str
    stage: str        # short machine-ish label, e.g. "needs-supplier"
    action: str       # one plain-language sentence: what to do now
    command: str      # the exact CLI command (empty when the action is off-engine)
    urgency: int      # 0 = informational … 3 = act today

    @property
    def line(self) -> str:
        mark = {3: "🔴", 2: "🟠", 1: "🟡", 0: "⚪"}[self.urgency]
        cmd = f"\n      $ {self.command}" if self.command else ""
        return f"{mark} {self.product_id:<18} [{self.stage}] {self.action}{cmd}"


def _cli(cmd: str) -> str:
    return f"python -m tt_engine.cli {cmd}"


def next_step(db: Database, product: models.Product) -> Step:
    pid = product.id

    metrics = db.metrics_for(pid)
    if len(metrics) < 7:
        return Step(pid, product.name, "needs-data",
                    f"Only {len(metrics)} day(s) of sales data. You need about a week to "
                    "see whether it is growing. Log it daily, or import a longer CSV.",
                    _cli(f"add-metric {pid} --units N --price P"), 1)

    if not db.suppliers_for(pid):
        return Step(pid, product.name, "needs-supplier",
                    "No supplier cost yet, so profit can't be worked out. Enter the real "
                    "price your supplier charges.",
                    _cli(f"add-supplier {pid} --cost X --ship-cost Y"), 2)

    score = db.latest_score(pid)
    today = _date.today().isoformat()
    if score is None or score.date != today:
        return Step(pid, product.name, "needs-score",
                    "New sales data has come in since this was last scored. Re-score it "
                    "before deciding anything.",
                    _cli(f"scorecard {pid}"), 1)

    # A recorded final outcome means this product's loop is closed.
    result = db.latest_result(pid)
    if result and result.decision in ("kill", "scale"):
        verb = "killed — move budget to the next candidate" if result.decision == "kill" \
            else "scaling — raise budget in ~30% steps while ROAS holds"
        return Step(pid, product.name, f"concluded-{result.decision}",
                    f"Outcome recorded: {verb}.", "", 0)

    if not score.gates_passed:
        blockers = "; ".join(score.gate_failures)
        fixable = any("margin" in f or "landed" in f for f in score.gate_failures)
        action = (f"Hard-gated: {blockers}. "
                  + ("A cheaper supplier could clear the margin floor — requote, else drop it."
                     if fixable else "Not fixable (compliance) — drop it and move on."))
        return Step(pid, product.name, "gated", action,
                    _cli(f"scorecard {pid}") if fixable else "", 1 if fixable else 0)

    if score.total < CONFIG.score_threshold:
        gap = CONFIG.score_threshold - score.total
        return Step(pid, product.name, "watch",
                    f"{score.total:.1f}/100 — {gap:.1f} points short of TEST. Keep logging "
                    "daily metrics; the score moves when momentum/saturation do.",
                    _cli(f"add-metric {pid} --units N --price P"), 1)

    # ── TEST verdict: walk the creative → launch → decide chain ────────────────
    tests = db.tests_for_product(pid)
    if tests:
        summary = summarize_tests(pid, tests)
        # Break-even from the stored supplier + latest price (cheap, no re-score).
        suppliers = db.suppliers_for(pid)
        best = min(suppliers, key=lambda s: s.cost + s.ship_cost)
        from .economics import compute_economics
        price = metrics[-1].price
        breakeven = compute_economics(price, best.cost, best.ship_cost).breakeven_roas
        decision = decide(summary, breakeven,
                          refund_rate=result.refund_rate if result else None, tests=tests)
        if decision.decision == "kill":
            return Step(pid, product.name, "kill-now",
                        f"KILL: {'; '.join(decision.reasons)}. Stop spend today and record it.",
                        _cli(f"log-result {pid} --decision kill"), 3)
        if decision.decision == "scale":
            return Step(pid, product.name, "scale-now",
                        f"SCALE: {'; '.join(decision.reasons)}. Record it, then raise "
                        "budget in ~30% steps while ROAS holds above break-even.",
                        _cli(f"log-result {pid} --decision scale"), 3)
        hours, _ = hours_below_breakeven(tests, breakeven)
        warn = (f" ⚠ {hours:.0f}h of the {KILL_HOURS:.0f}h below-break-even timer used."
                if hours else "")
        last_test_date = max(t.date for t in tests)
        if last_test_date < today:
            return Step(pid, product.name, "log-today",
                        f"Test is live but today's spend/revenue isn't logged.{warn}",
                        _cli(f"log-test {pid} --spend X --revenue Y"), 2)
        return Step(pid, product.name, "testing",
                    f"Watching: {'; '.join(decision.reasons)}.{warn}",
                    _cli(f"validate {pid}"), 1)

    creatives = [c for c in db.creatives_for(pid) if c.format != "Manual"]
    if creatives:
        ready = [c for c in creatives if c.status in ("ready", "exported")]
        if ready:
            exported = [c for c in ready if c.status == "exported"]
            if not exported:
                return Step(pid, product.name, "export",
                            f"{len(ready)} asset(s) generated — export the manifest "
                            "(AIGC disclosure is checked) and upload to TikTok.",
                            _cli(f"export-creatives {pid}"), 2)
            return Step(pid, product.name, "launch",
                        "Assets exported — launch small ad sets (spread the hooks), then "
                        "log spend/revenue here every day.",
                        _cli(f"log-test {pid} --spend X --revenue Y"), 2)
        if CONFIG.higgsfield_available:
            return Step(pid, product.name, "generate",
                        f"{len(creatives)} creative(s) planned — key + SDK configured; "
                        "confirm generation (this spends money).",
                        _cli(f"creative {pid} --confirm"), 2)
        return Step(pid, product.name, "configure-higgsfield",
                    f"{len(creatives)} creative(s) planned but HIGGSFIELD_API_KEY / the "
                    "higgsfield-client SDK isn't set up — add the key to .env and `pip "
                    "install higgsfield-client`, then confirm generation. (Or, in a "
                    "Claude Code session with the Higgsfield MCP connected, just ask the "
                    "agent to generate the batch directly.)",
                    _cli(f"creative {pid} --confirm"), 1)

    if not product.reviews:
        return Step(pid, product.name, "needs-psych",
                    "TEST verdict but no comments/reviews on file — paste the top "
                    "comments so psychology can drive the brief.",
                    _cli(f"psych {pid} --file comments.txt"), 2)

    return Step(pid, product.name, "build-creative",
                f"TEST verdict ({score.total:.0f}/100) — build the creative kit "
                "(dry-run is free; --confirm generates).",
                _cli(f"creative {pid}"), 2)


def all_steps(db: Database) -> list[Step]:
    """Every product's next step, most urgent first."""
    steps = [next_step(db, p) for p in db.all_products()]
    steps.sort(key=lambda s: (-s.urgency, s.product_id))
    return steps


def render_guide(db: Database, limit: Optional[int] = None) -> str:
    steps = all_steps(db)
    if not steps:
        return ("Nothing in the pipeline yet. Start with data:\n"
                f"  $ {_cli('import-csv exports/kalodata.csv --source kalodata')}\n"
                f"  $ {_cli('add --name ... --category ...')}")
    shown = steps[:limit] if limit else steps
    lines = ["What to do next (most urgent first):", ""]
    lines += [s.line for s in shown]
    if limit and len(steps) > limit:
        lines.append(f"… and {len(steps) - limit} more (run `next` with no limit)")
    return "\n".join(lines)
