"""Profit engineering — the levers that decide whether this business works.

Start with the thing that has to be said plainly: **no product-testing business is
always profitable, and any tool claiming otherwise is lying to you.** You are paying
to discover which products sell. Discovery has a cost and that cost lands as losses
on the products that don't. A per-test guarantee is not available at any price.

What IS available, and what this module computes:

  1. Make the LOSSES CHEAP     — screen candidates for cents before paying $150
  2. Make the SHOTS MANY       — P(≥1 winner) rises fast with attempts
  3. Make the WINS BIGGER      — margin is a bigger lever than volume
  4. Make the KILLS FAST       — the 48h rule caps the downside per test

Those four turn "profitable per test" (impossible) into "profitable per PORTFOLIO"
(achievable, and computable). That is the honest version of the question, and the
math below is the answer to it.

THE HEADLINE FINDING, which the roadmap already implies and this makes explicit:
$400,000 profit needs $2.5M of revenue at a blended 16% net margin, and $1.14M at
an organic-first 35% margin. Same profit, less than half the revenue. Every hour
spent raising margin is worth more than an hour spent raising volume — and the
organic-first screen below raises the hit rate and the margin at the same time.

Every rate here that is an ASSUMPTION says so and names the command that replaces it
with your measured number. The engine does not invent conversion rates any more than
it invents landed costs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ── Baseline rates. Assumptions until YOUR data replaces them. ────────────────
# Sources: the engine's own month-one model + the researched beginner bands. These
# are starting priors, not measurements. `report-monthly` recalibrates from outcomes.
P_WIN_COLD = 0.20          # a cold paid test on a decent candidate wins ~1 in 5
PAID_TEST_COST = 150.0     # the disciplined per-test budget
KILLED_TEST_LOSS = 90.0    # the 48h timer caps a loser here, not at the full budget
BLENDED_MARGIN = 0.16
ORGANIC_MARGIN = 0.35
WINNER_MONTHLY_PROFIT = 2_000.0   # a modest winner's monthly take-home once scaled

# Organic-first screening: post a few organic clips per candidate BEFORE paying for
# traffic, and only fund the ones that already earned views. The lift is the part
# you must verify yourself — it is the difference between a filter that works and a
# superstition. Treat it as a hypothesis your first 20 screens will confirm or kill.
ORGANIC_CLIPS_PER_SCREEN = 4
SCREEN_PASS_RATE = 0.25    # ASSUMPTION: ~1 in 4 candidates shows organic signal
SCREEN_LIFT = 2.0          # ASSUMPTION: screened candidates win ~2× as often as cold


def p_at_least_one(p_win: float, n: int) -> float:
    """Probability at least one of n independent tests wins."""
    if not 0.0 <= p_win <= 1.0 or n < 0:
        raise ValueError("p_win must be in [0,1] and n >= 0")
    return 1.0 - (1.0 - p_win) ** n


def shots_for_confidence(p_win: float, confidence: float = 0.90) -> int:
    """How many tests until P(≥1 winner) reaches `confidence`.

    This is the real answer to 'how do I make this a sure thing': you cannot make
    one test certain, but you can make one WINNER near-certain by affording enough
    attempts. Which is why cheap losses matter more than clever picking."""
    if not 0.0 < p_win < 1.0:
        raise ValueError("p_win must be strictly between 0 and 1")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")
    return math.ceil(math.log(1.0 - confidence) / math.log(1.0 - p_win))


@dataclass
class ScreenPlan:
    """Budget split between cheap organic screening and expensive paid tests."""
    budget: float
    clip_cost: Optional[float]
    candidates_screened: int
    screen_cost: float
    paid_tests: int
    paid_cost: float
    p_win_screened: float
    p_any_winner: float
    baseline_tests: int
    baseline_p_any: float

    @property
    def improvement(self) -> float:
        return self.p_any_winner - self.baseline_p_any

    def render(self) -> str:
        lines = ["## Organic-first screening vs. paying to find out", ""]
        if self.clip_cost is None:
            lines.append("Generation cost is UNPRICED — set TT_GENERATION_UNIT_COST to "
                         "compute how many candidates your budget can screen. The "
                         "structure below still holds; only the counts are missing.")
            return "\n".join(lines)
        lines += [
            f"  budget                    ${self.budget:,.0f}",
            "",
            "  COLD (pay to find out):",
            f"    {self.baseline_tests} paid tests × ${PAID_TEST_COST:.0f}",
            f"    P(at least one winner)  {self.baseline_p_any:.0%}",
            "",
            "  SCREENED (organic first, then pay to amplify):",
            f"    {self.candidates_screened} candidates screened organically "
            f"(${self.screen_cost:,.0f} total, "
            f"{ORGANIC_CLIPS_PER_SCREEN} clips each)",
            f"    {self.paid_tests} paid tests on what passed (${self.paid_cost:,.0f})",
            f"    P(at least one winner)  {self.p_any_winner:.0%}",
            "",
            f"  → {self.improvement:+.0%} on the odds of finding a winner, same money.",
        ]
        lines += [
            "",
            "  Why it works: a losing candidate costs "
            f"~${self.screen_cost / max(1, self.candidates_screened):.2f} to reject "
            f"instead of ~${KILLED_TEST_LOSS:.0f}. You are not picking better — you are "
            "buying far more attempts and only paying full price for the ones that "
            "already showed they can earn a view.",
            "",
            "  ⚠ SCREEN_PASS_RATE and SCREEN_LIFT are ASSUMPTIONS, not measurements. "
            "Screen your first 20 candidates, log what actually happened, and replace "
            "them. If screened candidates do NOT win more often than cold ones, this "
            "whole strategy is superstition and you should know that within a month.",
        ]
        return "\n".join(lines)


def screening_plan(budget: float, clip_cost: Optional[float] = None,
                   p_win_cold: float = P_WIN_COLD) -> ScreenPlan:
    """Split a budget between cheap organic screening and paid tests, and compare
    the odds against spending it all on cold paid tests."""
    if budget <= 0:
        raise ValueError("budget must be > 0")
    baseline_tests = int(budget // PAID_TEST_COST)
    baseline_p = p_at_least_one(p_win_cold, baseline_tests)
    p_screened = min(0.95, p_win_cold * SCREEN_LIFT)

    if clip_cost is None or clip_cost <= 0:
        return ScreenPlan(budget=budget, clip_cost=None, candidates_screened=0,
                          screen_cost=0.0, paid_tests=baseline_tests,
                          paid_cost=baseline_tests * PAID_TEST_COST,
                          p_win_screened=p_screened, p_any_winner=baseline_p,
                          baseline_tests=baseline_tests, baseline_p_any=baseline_p)

    screen_unit = clip_cost * ORGANIC_CLIPS_PER_SCREEN
    # Reserve most of the budget for paid tests; screening is cheap enough that a
    # small slice buys a lot of candidates.
    screen_budget = budget * 0.20
    candidates = int(screen_budget // screen_unit) if screen_unit > 0 else 0
    passed = int(candidates * SCREEN_PASS_RATE)
    paid_budget = budget - candidates * screen_unit
    paid_tests = min(passed, int(paid_budget // PAID_TEST_COST))

    return ScreenPlan(
        budget=budget, clip_cost=clip_cost, candidates_screened=candidates,
        screen_cost=candidates * screen_unit, paid_tests=paid_tests,
        paid_cost=paid_tests * PAID_TEST_COST, p_win_screened=p_screened,
        p_any_winner=p_at_least_one(p_screened, paid_tests),
        baseline_tests=baseline_tests, baseline_p_any=baseline_p)


@dataclass
class Lever:
    name: str
    effect: str
    detail: str
    how: str

    def render(self) -> str:
        return f"  {self.name}\n    {self.effect}\n    {self.detail}\n    → {self.how}"


def levers(target_profit: float, months: int = 24) -> list[Lever]:
    """The levers ranked by how much they actually move the target, computed."""
    blended_rev = target_profit / BLENDED_MARGIN
    organic_rev = target_profit / ORGANIC_MARGIN
    saved = blended_rev - organic_rev

    out = [
        Lever("1. MARGIN — make your own content instead of paying it out",
              f"cuts revenue needed from ${blended_rev:,.0f} to ${organic_rev:,.0f} "
              f"(−${saved:,.0f})",
              f"At a blended {BLENDED_MARGIN:.0%} net margin, ${target_profit:,.0f} "
              f"profit takes ${blended_rev:,.0f} of revenue. At an organic-first "
              f"{ORGANIC_MARGIN:.0%}, the same profit takes ${organic_rev:,.0f}. This is "
              "the largest single lever in the business and it is entirely under your "
              "control — it is what the AI creator roster is FOR.",
              "post organically first; use paid only to amplify what already works"),
        Lever("2. CHEAP LOSSES — screen organically before paying for traffic",
              f"a rejected candidate costs cents instead of ~${KILLED_TEST_LOSS:.0f}",
              "Most candidates lose. The cost of being wrong, not the rate of being "
              "right, is what drains a small budget. Screening converts most losses "
              "from $90 to roughly the price of four clips.",
              "`profit screen` sizes it against your real budget and clip cost"),
        Lever("3. SHOTS ON GOAL — enough attempts to make one winner near-certain",
              f"{shots_for_confidence(P_WIN_COLD, 0.90)} tests reach 90% odds of ≥1 "
              f"winner at a {P_WIN_COLD:.0%} hit rate",
              "One test is a coin flip you lose 80% of the time. Enough cheap tests "
              "make at least one winner close to inevitable. This is why lever 2 "
              "matters more than picking cleverly.",
              "keep per-test cost at $150 and never let one product eat the budget"),
        Lever("4. FAST KILLS — the 48-hour rule",
              f"caps a loser at ~${KILLED_TEST_LOSS:.0f} instead of ${PAID_TEST_COST:.0f}",
              "Already built and enforced. Its whole value is that it fires while you "
              "still feel optimistic. Overriding it once undoes the protection.",
              "`validate <id>` decides; you execute it without a vote"),
        Lever("5. SCALE THE WINNER — the payoff side",
              "a found winner compounds; a found loser is already capped",
              "Finding a winner is worth nothing if you scale it timidly or blow it up "
              "with a 3× budget jump. 20–30% steps, re-validating after each.",
              "`validate` after every raise; diversify creative before fatigue"),
    ]
    return out


@dataclass
class ProfitPlan:
    target: float
    months: int
    margin: float
    monthly_profit: float
    monthly_revenue: float
    revenue_total: float
    winners_needed: int
    orders_per_day: float

    def render(self) -> str:
        return "\n".join([
            f"  target                    ${self.target:,.0f} profit over "
            f"{self.months} months",
            f"  at {self.margin:.0%} net margin",
            f"  monthly profit needed     ${self.monthly_profit:,.0f}",
            f"  monthly revenue needed    ${self.monthly_revenue:,.0f}",
            f"  cumulative revenue        ${self.revenue_total:,.0f}",
            f"  orders/day at $45 AOV     ~{self.orders_per_day:.0f}",
            f"  concurrent winners        ~{self.winners_needed}",
        ])


def plan_profit(target: float = 400_000.0, months: int = 24,
                margin: float = ORGANIC_MARGIN, aov: float = 45.0) -> ProfitPlan:
    if target <= 0 or months <= 0:
        raise ValueError("target and months must be > 0")
    if not 0 < margin <= 1:
        raise ValueError("margin must be a fraction in (0, 1]")
    monthly_profit = target / months
    monthly_revenue = monthly_profit / margin
    return ProfitPlan(
        target=target, months=months, margin=margin,
        monthly_profit=monthly_profit, monthly_revenue=monthly_revenue,
        revenue_total=monthly_revenue * months,
        winners_needed=max(1, math.ceil(monthly_revenue / 40_000.0)),
        orders_per_day=monthly_revenue / aov / 30.0)


def render(target: float = 400_000.0, months: int = 24, budget: float = 1_180.0,
           clip_cost: Optional[float] = None) -> str:
    blended = plan_profit(target, months, BLENDED_MARGIN)
    organic = plan_profit(target, months, ORGANIC_MARGIN)

    lines = [f"# ${target:,.0f} profit — what it actually takes", ""]
    lines.append("## First, the honest part")
    lines.append(
        "  No product-testing business is profitable on every test. You are paying to\n"
        "  discover which products sell, and discovery costs money on the ones that\n"
        "  don't. Anything promising per-test profitability is selling you something.\n"
        "\n"
        "  What IS achievable is PORTFOLIO profitability: make the losses cheap, the\n"
        "  attempts many, the wins big, and the kills fast. Then one winner pays for\n"
        "  every loser that found it. That is a solvable problem, and the math is below.")
    lines.append("")

    lines.append(f"## The target, two ways ({months} months)")
    lines.append("")
    lines.append(f"  AT BLENDED {BLENDED_MARGIN:.0%} MARGIN (paying creators/affiliates):")
    lines.append(blended.render())
    lines.append("")
    lines.append(f"  AT ORGANIC-FIRST {ORGANIC_MARGIN:.0%} MARGIN (your own content):")
    lines.append(organic.render())
    lines.append("")
    saved = blended.revenue_total - organic.revenue_total
    lines.append(f"  → Same ${target:,.0f} profit. ${saved:,.0f} less revenue to build.")
    lines.append("    Margin is not a detail; it is most of the mountain.")
    lines.append("")

    lines.append("## The levers, ranked by what they actually move")
    lines.append("")
    for lever in levers(target, months):
        lines.append(lever.render())
        lines.append("")

    lines.append(screening_plan(budget, clip_cost).render())
    lines.append("")

    lines.append("## Shots on goal — the portfolio view")
    lines.append("")
    lines.append(f"  At a {P_WIN_COLD:.0%} per-test hit rate:")
    for n in (1, 3, 5, 7, 10, 14, 20):
        lines.append(f"    {n:2d} tests → {p_at_least_one(P_WIN_COLD, n):5.0%} chance of "
                     "at least one winner")
    lines.append("")
    lines.append("  One test is a coin flip you lose four times out of five. Fourteen\n"
                 "  cheap tests make a winner ~95% likely. The strategy is not to pick\n"
                 "  better than everyone else — it is to afford more attempts than they\n"
                 "  can, which is exactly what organic screening buys.")
    lines.append("")
    lines.append("## What this does NOT promise")
    lines.append(
        "  • Not that any individual test profits — most will not.\n"
        "  • Not that month one profits — it is planned to lose about $247.\n"
        f"  • Not that ${target:,.0f} arrives in {months} months. It is a target that\n"
        "    tells you what scale is required, not a forecast that it happens.\n"
        "  • P_WIN, SCREEN_PASS_RATE and SCREEN_LIFT are assumptions. Measure them\n"
        "    against your own first 20 candidates and replace them — `report-monthly`\n"
        "    exists to make that a habit rather than an intention.")
    return "\n".join(lines)
