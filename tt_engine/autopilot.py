"""Autopilot: the whole loop runs itself — behind an approval gate on every step.

How it works (the operator's ask: "automated, but each step needs my approval
first"):

  1. `run` reads the live DB through the operator guide and PROPOSES the next
     action for every product as a queue item. Proposing is free and safe —
     nothing has happened yet.
  2. Nothing executes until the operator approves the item (`approve <id>`, or
     the dashboard link for internal steps). Approval executes it immediately
     and records the result.
  3. When trust is earned, individual INTERNAL stages can be flipped to 'auto'
     (`policy <stage> auto`) — those execute on sight during `run`, still
     recorded in the queue as an audit trail.

The permission model is three kinds, and it is not negotiable:

  internal  — pure computation or safe state-recording (re-score, plan a
              creative pack, export a manifest, record a kill/scale decision).
              Approval-gated by default; MAY be flipped to auto.
  external  — spends money, publishes, or contacts someone (today: Higgsfield
              generation). Approval is the founding guardrail's "explicit
              confirmation" — these can NEVER be set to auto. Ever.
  manual    — performed by the operator off-engine (add a supplier quote,
              upload to TikTok, log today's spend). The queue shows the exact
              command; the item clears ITSELF when the DB state advances —
              un-fakeable, like the playbook's auto steps.

Stale items supersede automatically: when a product's guide stage moves on, its
old queue items are marked 'superseded' — the queue always mirrors reality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Optional

from . import pipeline
from .db import Database, models
from .guide import Step, all_steps

# Stages the engine can execute itself, and how much trust each needs.
INTERNAL_STAGES = ("needs-score", "build-creative", "export", "kill-now", "scale-now")
EXTERNAL_STAGES = ("generate",)          # spends money — approval REQUIRED, forever
_DONE_STAGES = ("concluded-kill", "concluded-scale")


def kind_for(stage: str) -> str:
    if stage in INTERNAL_STAGES:
        return "internal"
    if stage in EXTERNAL_STAGES:
        return "external"
    return "manual"


# ── execution (what approval actually triggers) ─────────────────────────────────
def _exec_needs_score(db: Database, pid: str) -> str:
    sr = pipeline.score_stored(db, pid)
    if sr is None:
        raise ValueError(f"{pid}: no stored metrics to score")
    db.upsert_score(sr.breakdown.score)
    s = sr.breakdown.score
    return (f"re-scored: {s.total:.1f}/100, gates "
            f"{'PASS' if s.gates_passed else 'FAIL (' + ', '.join(s.gate_failures) + ')'}")


def _exec_build_creative(db: Database, pid: str) -> str:
    from .creative.mcp_client import ConfirmationRequired
    try:
        _kit, res = pipeline.produce_creatives(db, pid, confirm=False)
    except ConfirmationRequired:
        return ("creative kit briefed — generation is configured and costs money, "
                "so it stays a separate approval (the 'generate' step)")
    return f"creative kit planned: {len(res.creatives)} asset(s) briefed (no spend)"


def _exec_generate(db: Database, pid: str) -> str:
    _kit, res = pipeline.produce_creatives(db, pid, confirm=True)
    return f"generation run: {res.summary.splitlines()[0]}"


def _exec_export(db: Database, pid: str) -> str:
    from .creative.mcp_client import export_creatives
    res = export_creatives(db, pid, f"out/manifest_{pid}.md")
    return (f"export: {len(res.exported)} exported, {len(res.blocked)} BLOCKED on "
            f"missing AIGC disclosure, {len(res.not_ready)} not generated yet")


def _exec_record(decision: str):
    def _run(db: Database, pid: str) -> str:
        db.upsert_result(models.Result(product_id=pid,
                                       date=_date.today().isoformat(),
                                       decision=decision))
        verb = ("stop all spend today; move budget to the next candidate"
                if decision == "kill"
                else "raise budget in ~30% steps while ROAS holds above break-even")
        return f"{decision.upper()} recorded — {verb}"
    return _run


_EXECUTORS = {
    "needs-score": _exec_needs_score,
    "build-creative": _exec_build_creative,
    "generate": _exec_generate,
    "export": _exec_export,
    "kill-now": _exec_record("kill"),
    "scale-now": _exec_record("scale"),
}


# ── the pass ────────────────────────────────────────────────────────────────────
@dataclass
class RunReport:
    proposed: list[dict] = field(default_factory=list)
    auto_executed: list[dict] = field(default_factory=list)
    superseded: list[dict] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)

    @property
    def headline(self) -> str:
        return (f"{len(self.proposed)} newly proposed · "
                f"{len(self.auto_executed)} auto-executed · "
                f"{len(self.superseded)} superseded · "
                f"{len(self.pending)} awaiting your approval")


def run(db: Database) -> RunReport:
    """One autopilot pass: supersede stale items, propose next steps, auto-execute
    only what policy explicitly allows. Idempotent — safe to run on a cron."""
    report = RunReport()
    steps: list[Step] = [s for s in all_steps(db) if s.stage not in _DONE_STAGES]
    current = {(s.product_id, s.stage): s for s in steps}
    policy = db.autopilot_policy()

    # 1. Supersede pending items whose stage the world has moved past.
    for item in db.autopilot_actions(status="pending"):
        if (item["product_id"], item["stage"]) not in current:
            db.set_autopilot_status(item["id"], "superseded",
                                    "state advanced — this step is no longer next")
            report.superseded.append(item)

    # 2. Propose anything actionable that isn't already queued. A rejection sticks
    #    while the stage is unchanged — the queue doesn't nag; the world moving on
    #    (new stage) is what re-opens proposals for a product.
    open_keys = {(i["product_id"], i["stage"])
                 for i in db.autopilot_actions(status="pending")}
    open_keys |= {(i["product_id"], i["stage"])
                  for i in db.autopilot_actions(status="rejected")}
    for step in steps:
        if step.urgency < 1 or (step.product_id, step.stage) in open_keys:
            continue
        kind = kind_for(step.stage)
        aid = db.add_autopilot_action(step.product_id, step.stage, kind,
                                      step.action, step.command)
        item = db.autopilot_action(aid)
        report.proposed.append(item)

        # 3. Auto-execute ONLY internal stages the operator explicitly flipped.
        if kind == "internal" and policy.get(step.stage) == "auto":
            try:
                result = _EXECUTORS[step.stage](db, step.product_id)
                db.set_autopilot_status(aid, "executed", f"[auto] {result}")
                report.auto_executed.append(db.autopilot_action(aid))
            except Exception as e:                     # noqa: BLE001 — audit, don't crash the pass
                db.set_autopilot_status(aid, "pending", f"auto-exec failed: {e}")

    report.pending = db.autopilot_actions(status="pending")
    return report


def approve(db: Database, action_id: int) -> str:
    """Execute one approved step. Approval IS the explicit confirmation the
    guardrail requires — which is why it must come from the operator, per item."""
    item = db.autopilot_action(action_id)
    if item is None:
        raise ValueError(f"no queue item #{action_id}")
    if item["status"] != "pending":
        raise ValueError(f"#{action_id} is already {item['status']} — nothing to approve")
    if item["kind"] == "manual":
        raise ValueError(
            f"#{action_id} ({item['stage']}) is performed by YOU, off-engine: "
            f"{item['description']}" + (f"\n  $ {item['command']}" if item["command"]
                                        else "") +
            "\nIt clears itself from the queue once the DB shows the work.")
    result = _EXECUTORS[item["stage"]](db, item["product_id"])
    db.set_autopilot_status(action_id, "executed", result)
    return result


def reject(db: Database, action_id: int, why: str = "") -> None:
    item = db.autopilot_action(action_id)
    if item is None or item["status"] != "pending":
        raise ValueError(f"no pending queue item #{action_id}")
    db.set_autopilot_status(action_id, "rejected", why or "rejected by operator")


def set_policy(db: Database, stage: str, mode: str) -> str:
    if mode not in ("approve", "auto"):
        raise ValueError("mode must be 'approve' or 'auto'")
    if stage in EXTERNAL_STAGES:
        raise ValueError(
            f"'{stage}' spends money — the founding guardrail says every external "
            "action requires explicit confirmation. It can never be set to auto.")
    if stage not in INTERNAL_STAGES:
        raise ValueError(
            f"'{stage}' is performed by you off-engine — there is nothing to "
            f"automate. Auto-executable stages: {', '.join(INTERNAL_STAGES)}")
    db.set_autopilot_policy(stage, mode)
    return (f"{stage}: {mode}" +
            (" — will execute on sight during `autopilot run`" if mode == "auto"
             else " — back to per-item approval"))


def render_queue(db: Database) -> str:
    items = db.autopilot_actions()
    policy = db.autopilot_policy()
    lines = ["# Autopilot queue", ""]
    pending = [i for i in items if i["status"] == "pending"]
    if pending:
        lines.append("## Awaiting your approval")
        for i in pending:
            tag = {"internal": "safe — runs on approve",
                   "external": "SPENDS MONEY — approve = explicit confirmation",
                   "manual": "yours to do off-engine; clears itself when done"}[i["kind"]]
            lines.append(f"  #{i['id']:<4} {i['product_id']:<16} [{i['stage']}] ({tag})")
            lines.append(f"        {i['description']}")
            if i["command"]:
                lines.append(f"        $ {i['command']}")
            if i["kind"] != "manual":
                lines.append(f"        approve: python -m tt_engine.cli autopilot "
                             f"approve {i['id']}")
            lines.append("")
    else:
        lines += ["(nothing pending — run `autopilot run` to refresh proposals)", ""]
    done = [i for i in items if i["status"] in ("executed", "rejected")][-8:]
    if done:
        lines.append("## Recent decisions")
        lines += [f"  #{i['id']:<4} {i['product_id']:<16} [{i['stage']}] "
                  f"{i['status']}: {i['result']}" for i in done]
        lines.append("")
    auto = [s for s in INTERNAL_STAGES if policy.get(s) == "auto"]
    auto_desc = ", ".join(auto) if auto else "(none — every step asks first, as configured)"
    lines.append(f"POLICY: auto = {auto_desc}; external stages "
                 f"({', '.join(EXTERNAL_STAGES)}) always require approval.")
    return "\n".join(lines)
