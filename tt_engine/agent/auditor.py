"""The auditor — one agent that evaluates the whole business and tells you what's wrong.

Every other module answers a question you thought to ask. This one asks the questions
for you: it sweeps every domain (money, data, economics, testing discipline, creative,
compliance, account health, readiness) and returns ranked findings, each with the exact
command that fixes it.

Two layers, and the split matters:

  • The RULES layer is deterministic and always runs. Every check is arithmetic or a
    fact read from your database — no model in the loop, no network, nothing to
    hallucinate. If it says "you have 3 products with no landed cost," that is a
    count, not an opinion.

  • The JUDGMENT layer (ANTHROPIC_API_KEY set) reads the rules layer's findings plus
    the compiled business state and adds what arithmetic can't see: which finding
    actually matters most this week, patterns across findings, and what a competent
    operator would do next. It is clearly labeled, it can only ADD commentary, and it
    can never delete, downgrade, or contradict a rules finding — a model talking you
    out of a real problem is the exact failure mode worth designing against.

The auditor never fixes anything. It names the command; you run it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..db import Database

CRITICAL, WARNING, INFO, GOOD = "critical", "warning", "info", "good"
_RANK = {CRITICAL: 0, WARNING: 1, INFO: 2, GOOD: 3}


@dataclass
class Finding:
    severity: str
    domain: str
    title: str
    detail: str
    fix: str = ""                  # the exact command or action that resolves it
    money: str = ""                # what this costs if ignored — blank when nothing

    def render(self) -> str:
        mark = {CRITICAL: "🔴", WARNING: "🟡", INFO: "🔵", GOOD: "🟢"}[self.severity]
        out = [f"{mark} [{self.domain}] {self.title}", f"     {self.detail}"]
        if self.money:
            out.append(f"     COSTS: {self.money}")
        if self.fix:
            out.append(f"     FIX:   {self.fix}")
        return "\n".join(out)


@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)
    judgment: str = ""
    judgment_mode: str = "offline"

    @property
    def criticals(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == CRITICAL]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def score(self) -> int:
        """A blunt 0–100 readiness number. Criticals hurt hard because they are the
        ones that lose money or close accounts; info items don't move it."""
        if not self.findings:
            return 100
        penalty = 25 * len(self.criticals) + 8 * len(self.warnings)
        return max(0, 100 - penalty)

    def render(self) -> str:
        lines = ["# Audit — everything the engine can check about your business", ""]
        lines.append(f"readiness {self.score}/100 · {len(self.criticals)} critical · "
                     f"{len(self.warnings)} warning · {len(self.findings)} total")
        lines.append("")
        by_domain: dict[str, list[Finding]] = {}
        for f in sorted(self.findings, key=lambda f: (_RANK[f.severity], f.domain)):
            by_domain.setdefault(f.domain, []).append(f)
        for domain, items in by_domain.items():
            lines.append(f"## {domain}")
            lines += [f.render() for f in items]
            lines.append("")
        if self.judgment:
            label = ("Claude's read on the above" if self.judgment_mode == "llm"
                     else "Priority read (offline — deterministic ordering)")
            lines += [f"## {label}", self.judgment, ""]
        if not self.criticals:
            lines.append("No criticals. That means nothing is actively bleeding — it "
                         "does NOT mean a product will work. That part is still the market's call.")
        return "\n".join(lines)


# ── the rules layer ───────────────────────────────────────────────────────────
# Each check takes the db and returns findings. Registered in CHECKS below.

def check_spend_guards(db: Database) -> list[Finding]:
    from ..creative import spend
    out: list[Finding] = []
    if spend.unit_cost() is None:
        out.append(Finding(
            WARNING, "money", "Generation cost is unpriced",
            "The confirm gate can tell you THAT a batch spends money but not how much. "
            "You cannot meaningfully approve a number you were never shown.",
            fix="set TT_GENERATION_UNIT_COST=<your real per-clip cost> in .env",
            money="an unbounded approval — you find out the size after paying"))
    if spend.spend_ceiling() is None:
        out.append(Finding(
            WARNING, "money", "No per-batch spend ceiling",
            f"Only the {spend.MAX_BATCH}-clip size cap protects you. A ceiling refuses "
            "an over-budget batch even when --confirm is passed.",
            fix="set TT_MAX_BATCH_SPEND=<dollars> in .env",
            money="one mistyped batch at full size"))
    orphans = [c for c in db.all_creatives()
               if c.status == "generating" and c.meta.get("job_id")]
    if orphans:
        out.append(Finding(
            CRITICAL, "money", f"{len(orphans)} paid job(s) never landed",
            "Generation is charged at submit. These were submitted and paid for but the "
            "assets were never collected. They are still recoverable.",
            fix="python -m tt_engine.cli creative-recover",
            money=f"the full cost of {len(orphans)} clip(s), already spent"))
    return out


def check_landed_costs(db: Database) -> list[Finding]:
    out: list[Finding] = []
    products = db.all_products()
    if not products:
        return out
    missing = [p for p in products if not db.suppliers_for(p.id)]
    if missing:
        names = ", ".join(p.name[:28] for p in missing[:4])
        out.append(Finding(
            WARNING, "economics", f"{len(missing)} product(s) have no landed cost",
            f"Economics cannot be scored without a real supplier quote ({names}"
            f"{'…' if len(missing) > 4 else ''}). The engine refuses to guess, so these "
            "products carry no margin, break-even ROAS, or max-CAC numbers.",
            fix="add-supplier <product_id> --cost X --ship-cost Y",
            money="you would be setting ad budgets against an unknown margin"))
    return out


def _breakeven_roas(db: Database, product_id: str) -> float:
    """The break-even the kill timer measures against. Infinity when there is no real
    landed cost — the engine refuses to invent one, so no test can be judged either."""
    suppliers = db.suppliers_for(product_id)
    metrics = db.metrics_for(product_id)
    if not suppliers or not metrics:
        return float("inf")
    from ..economics import compute_economics
    best = min(suppliers, key=lambda s: s.cost + s.ship_cost)
    return compute_economics(metrics[-1].price, best.cost, best.ship_cost).breakeven_roas


def check_test_discipline(db: Database) -> list[Finding]:
    """The 48-hour timer only works if someone actually looks at it."""
    from ..validation import KILL_HOURS, hours_below_breakeven
    out: list[Finding] = []
    for p in db.all_products():
        tests = db.tests_for_product(p.id)
        if not tests:
            continue
        be = _breakeven_roas(db, p.id)
        if be == float("inf"):
            out.append(Finding(
                WARNING, "testing", f"{p.name[:36]} is running with no break-even",
                "Live ad tests are logged but there is no landed cost, so break-even "
                "ROAS is unknown and the kill timer cannot fire. You are spending "
                "without a defined losing condition.",
                fix=f"add-supplier {p.id} --cost X --ship-cost Y",
                money="ad spend with no rule that can stop it"))
            continue
        hours, _ = hours_below_breakeven(tests, be)
        if hours >= KILL_HOURS:
            out.append(Finding(
                CRITICAL, "testing", f"{p.name[:36]} is {hours:.0f}h below break-even",
                f"The {KILL_HOURS:.0f}-hour kill rule has already fired. Every further "
                "hour of spend buys information you already have.",
                fix=f"validate {p.id} && log-result {p.id} --decision kill",
                money="continued daily ad spend on a product the rule already killed"))
    return out


def check_compliance(db: Database) -> list[Finding]:
    out: list[Finding] = []
    undisclosed = [c for c in db.all_creatives()
                   if c.status in ("ready", "exported", "posted")
                   and not c.meta.get("aigc_disclosure")]
    if undisclosed:
        out.append(Finding(
            CRITICAL, "compliance", f"{len(undisclosed)} asset(s) missing AIGC disclosure",
            "Undisclosed AI content is reportedly the most common Level-1 warning cause. "
            "The export path blocks these, but they should not exist at all.",
            fix="regenerate through the pipeline (it writes the disclosure automatically)",
            money="a policy strike against the shop, which is the whole business"))
    return out


def check_capital(db: Database) -> list[Finding]:
    """Undercapitalization is not a style choice — it decides whether you can survive
    the losing tests that pay for the winner."""
    from ..capital import plan_capital
    plan = plan_capital(capital=2000.0, test_budget=150.0,
                        daily_ad_spend=15.0, daily_cogs=7.0)
    out: list[Finding] = []
    for w in plan.warnings:
        out.append(Finding(
            WARNING, "capital", "Capital plan warning", w,
            fix="capital --capital <your real number> --test-budget 150",
            money="running out of runway before a winner is found"))
    if not plan.warnings:
        out.append(Finding(
            GOOD, "capital", "Capital envelope is clean",
            f"${plan.deployable:,.0f} deployable · {plan.max_concurrent_tests} concurrent "
            f"tests · {plan.runway_months:.1f} months runway, at $150/test and $15/day ads."))
    return out


def check_catalog_demand_gap(db: Database) -> list[Finding]:
    """Catalog import gives you hundreds of costed products and zero demand signal.
    That asymmetry is the trap: a cheap product with a fat theoretical margin and no
    demand looks like a find right up until the ad spend."""
    products = db.all_products()
    if not products:
        return []
    costed = [p for p in products if db.suppliers_for(p.id)]
    if not costed:
        return []
    no_demand = [p for p in costed if not db.metrics_for(p.id)]
    if not no_demand:
        return []
    share = len(no_demand) / len(costed)
    sev = WARNING if share > 0.9 else INFO
    return [Finding(
        sev, "product", f"{len(no_demand)} of {len(costed)} costed products have no "
        "demand data",
        "A supplier catalog carries cost and shipping but nothing about whether "
        "anything sells. These cannot reach a TEST verdict, and the supply ranking "
        "deliberately does not try to make them.",
        fix="pick 3 from `catalog rank`, research real demand, then `import-csv` "
            "or `add-metric` what you find",
        money="none yet — this is the gate that stops you spending on an untested guess")]


def check_data_freshness(db: Database) -> list[Finding]:
    out: list[Finding] = []
    products = db.all_products()
    if not products:
        out.append(Finding(
            WARNING, "data", "No products in the database",
            "Nothing can be scored, ranked, or tested until real market data is in. "
            "Momentum needs a multi-day series — one day tells you nothing.",
            fix="import-csv <file.csv> --source kalodata   (or `add` for a hand-found product)",
            money="none directly — but this is the gate on everything that earns"))
    return out


def check_wiring(db: Database) -> list[Finding]:
    from ..config import CONFIG
    out: list[Finding] = []
    if not CONFIG.higgsfield_available:
        out.append(Finding(
            INFO, "wiring", "Higgsfield not configured",
            "Creative is planned and briefed but never generated. This is the safe "
            "default, not a failure — the whole pipeline runs offline without it.",
            fix="set HIGGSFIELD_API_KEY + HF_KEY in .env, pip install higgsfield-client"))
    if not CONFIG.tiktok_posting_available:
        out.append(Finding(
            INFO, "wiring", "Official TikTok posting not configured",
            "Assets are prepared and exported; you upload them by hand. The engine will "
            "never use an unofficial poster.",
            fix="set TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_ACCESS_TOKEN"))
    if not CONFIG.llm_available:
        out.append(Finding(
            INFO, "wiring", "Claude not configured — auditor runs rules-only",
            "Every check above is deterministic and still ran. The judgment layer "
            "(prioritisation, cross-finding patterns) is what's missing.",
            fix="set ANTHROPIC_API_KEY in .env"))
    return out


def check_readiness(db: Database) -> list[Finding]:
    from ..playbook import overall
    done, total = overall(db)
    pct = (100 * done // total) if total else 0
    sev = INFO if pct >= 60 else WARNING
    return [Finding(
        sev, "readiness", f"Playbook {done}/{total} steps ({pct}%)",
        "Business foundations (entity, bank, tax, platform accounts) gate everything "
        "downstream. The engine cannot do these for you.",
        fix="python -m tt_engine.cli playbook   — then `check <step-id>` as you finish each")]


CHECKS: list[Callable[[Database], list[Finding]]] = [
    check_spend_guards,
    check_compliance,
    check_test_discipline,
    check_landed_costs,
    check_catalog_demand_gap,
    check_capital,
    check_data_freshness,
    check_readiness,
    check_wiring,
]


def run_rules(db: Database) -> list[Finding]:
    """Every deterministic check. A single broken check must never take the audit
    down — a partial audit is useful, a crashed one is not."""
    out: list[Finding] = []
    for check in CHECKS:
        try:
            out.extend(check(db) or [])
        except Exception as e:                      # noqa: BLE001 — resilience is the point
            out.append(Finding(
                INFO, "auditor", f"check `{check.__name__}` failed to run",
                f"{type(e).__name__}: {e}. The other checks still ran; this one is "
                "reporting itself rather than silently skipping."))
    return out


# ── the judgment layer ────────────────────────────────────────────────────────

_SYSTEM = """You are the auditor for a solo operator's TikTok Shop business engine.

You are given deterministic findings produced by arithmetic over their real database,
plus their live business state. Your job is to add judgment the arithmetic cannot:
what actually matters most this week, patterns across findings, and the single next
action.

Hard rules:
- NEVER contradict, downgrade, or explain away a finding. They are facts, not opinions.
- NEVER invent a number. If it is not in the context, say which command computes it.
- The operator may be working from borrowed money. Be direct and useful, not reassuring.
- Most first product tests lose money. Never imply a winner is likely.
- End with ONE concrete next action, naming the exact command.
Answer in under 200 words, plain prose, no preamble."""


def judgment(db: Database, findings: list[Finding], llm=None) -> tuple[str, str]:
    """Returns (text, mode). Falls back to deterministic prioritisation offline."""
    from ..llm import LLMClient, LLMUnavailable
    client = llm if llm is not None else LLMClient()
    ranked = sorted(findings, key=lambda f: _RANK[f.severity])

    if getattr(client, "available", False):
        context = "\n".join(f"[{f.severity}] {f.domain}: {f.title} — {f.detail}"
                            + (f" FIX: {f.fix}" if f.fix else "")
                            for f in ranked)
        try:
            from ..assistant import build_context
            state = build_context(db)
        except Exception:
            state = "(business state unavailable)"
        try:
            text = client.complete_text(
                _SYSTEM, f"FINDINGS:\n{context}\n\nBUSINESS STATE:\n{state}")
            return text.strip(), "llm"
        except LLMUnavailable:
            pass                                    # fall through to offline

    top = [f for f in ranked if f.severity in (CRITICAL, WARNING)][:3]
    if not top:
        return ("Nothing critical or warning-level is outstanding. The engine's checks "
                "are clean, which means nothing is bleeding — it does not mean a product "
                "will work. Next: `find --top 5` to rank what you have.", "offline")
    lines = ["In priority order, because severity is the only ordering arithmetic can defend:"]
    for i, f in enumerate(top, 1):
        lines.append(f"{i}. {f.title} — {f.fix or 'see the finding above'}")
    tail = (f"Ignoring it costs: {top[0].money}." if top[0].money
            else "It is the highest-severity item open.")
    lines.append(f"\nStart with #1. {tail}")
    return "\n".join(lines), "offline"


def audit(db: Database, llm=None, with_judgment: bool = True) -> AuditReport:
    """The whole sweep. Rules always run; judgment is additive and always labeled."""
    findings = run_rules(db)
    report = AuditReport(findings=findings)
    if with_judgment:
        report.judgment, report.judgment_mode = judgment(db, findings, llm=llm)
    return report
