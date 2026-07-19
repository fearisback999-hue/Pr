"""Road to $1M — the milestone math, honestly.

"Make a million" is two very different targets, and conflating them is how people set
themselves up to quit:

  • $1M in REVENUE (lifetime GMV) — a hard but well-trodden milestone. Survivors reach it.
  • $1M in PROFIT (take-home) — a different order of magnitude. At a realistic blended
    net margin (~15–18%), $1M/yr profit needs ~$5–7M/yr revenue, which is roughly top-1%
    -of-all-sellers execution. $1M CUMULATIVE profit over several good years is the
    attainable version of that.

This module computes what a given target actually requires — monthly revenue, orders/day,
how many concurrent winning products, the implied ad budget — and places it honestly in
the real seller distribution, then lays out the milestone ladder with the survival odds
at each rung. It sells nothing. Per Part 0's thesis: build for the skill and the system
(near-certain payoff); treat the $1M as the low-probability upside on top.

All benchmark numbers are from live research on 2026-07-09 (sources at the bottom of
render_roadmap / the dashboard page). They're snapshots — re-verify, platforms move.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

VERIFIED_DATE = "2026-07-09"

# ── researched benchmarks (TikTok Shop US, 2026) ────────────────────────────────
AOV_DEFAULT = 45.0            # platform AOV ~$35–45; beauty/apparel ~$63; sweet spot $40–80
BLENDED_MARGIN = 0.16         # ads+affiliate sellers 10–18%; organic-first 35–39%; avg 18.4%
ORGANIC_MARGIN = 0.35        # organic-first (you make the content, skip affiliate cut)
# Seller revenue distribution (monthly GMV), for honest percentile placement.
MEDIAN_SELLER_MO = 1_150.0
AVG_ACTIVE_SELLER_MO = 3_750.0
TOP1PCT_SELLER_MO = 215_000.0
# A single winning product tends to ceiling here before fatigue/saturation force the next
# one (top sellers share the "3+ viral products" trait) — a planning heuristic, not a law.
WINNER_CEILING_MO = 40_000.0
# Rough blended return on ad spend once a product works (organic reach dilutes paid).
TARGET_BLENDED_ROAS = 3.0
PAID_REVENUE_SHARE = 0.6      # assume ~60% of revenue is paid-driven, 40% organic/affiliate
# Etsy POD parallel stream: $50–100/mo per established listing.
POD_REV_PER_LISTING_MO = 75.0


@dataclass
class Milestone:
    name: str
    monthly_revenue: float       # the rung, in monthly GMV
    detail: str
    odds: str                    # honest survival/attainment note
    is_goal: bool = False        # the user's target lands at/above this rung


@dataclass
class MillionDollarPlan:
    goal_amount: float
    goal_type: str               # "revenue" | "profit"
    horizon_months: int
    aov: float
    net_margin: float
    # ── derived ────────────────────────────────────────────────────────────────
    monthly_revenue_needed: float
    monthly_profit_at_target: float
    cumulative_revenue_needed: float
    orders_per_day: float
    units_per_day: float
    winners_needed: int
    monthly_ad_budget: float
    percentile: str
    milestones: list[Milestone] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        goal_lbl = f"${self.goal_amount:,.0f} {self.goal_type}"
        lines = [
            f"GOAL: {goal_lbl} over {self.horizon_months} months "
            f"(AOV ${self.aov:.0f}, net margin {self.net_margin*100:.0f}%)",
            "",
            f"  need ~${self.monthly_revenue_needed:,.0f}/mo revenue  "
            f"(= ${self.monthly_profit_at_target:,.0f}/mo profit)",
            f"  = ~{self.orders_per_day:.0f} orders/day "
            f"(~{self.units_per_day:.0f} units/day at this AOV)",
            f"  = ~{self.winners_needed} concurrent winning product(s) at scale",
            f"  implied ad budget ~${self.monthly_ad_budget:,.0f}/mo "
            f"(at {TARGET_BLENDED_ROAS:.1f}x blended ROAS, {PAID_REVENUE_SHARE*100:.0f}% paid)",
            f"  cumulative revenue to get there: ~${self.cumulative_revenue_needed:,.0f}",
            "",
            f"  reality check: {self.percentile}",
        ]
        if self.notes:
            lines += [""] + [f"  • {n}" for n in self.notes]
        lines += ["", "MILESTONE LADDER (survive the early rungs first):", ""]
        for m in self.milestones:
            mark = " ◀ YOUR GOAL LANDS HERE" if m.is_goal else ""
            lines.append(f"  ${m.monthly_revenue:>9,.0f}/mo  {m.name}{mark}")
            lines.append(f"              {m.detail}")
            lines.append(f"              odds: {m.odds}")
            lines.append("")
        return "\n".join(lines)


def _percentile(monthly_rev: float) -> str:
    if monthly_rev < MEDIAN_SELLER_MO:
        return (f"below the median seller (~${MEDIAN_SELLER_MO:,.0f}/mo) — most shops live "
                "here; this is the honest starting reality, not failure")
    if monthly_rev < AVG_ACTIVE_SELLER_MO:
        return (f"between the median (~${MEDIAN_SELLER_MO:,.0f}) and the average active "
                f"seller (~${AVG_ACTIVE_SELLER_MO:,.0f}/mo) — a real, working shop")
    if monthly_rev < 50_000:
        return (f"above the average active seller (~${AVG_ACTIVE_SELLER_MO:,.0f}/mo) — solid "
                "operator territory; only ~1.5% of stores ever clear $50k total")
    if monthly_rev < TOP1PCT_SELLER_MO:
        return (f"$50k–${TOP1PCT_SELLER_MO/1000:.0f}k/mo — approaching the top 1% of US "
                "sellers, who drive ~60% of all GMV; a genuine brand, not a side hustle")
    return (f"at/above ~${TOP1PCT_SELLER_MO:,.0f}/mo you're in top-1% territory — the "
            "0.1% who account for a quarter of all TikTok Shop GMV. Rare, and real.")


def _milestones(monthly_rev_goal: float) -> list[Milestone]:
    """Fixed revenue rungs with honest odds; the goal is flagged on whichever it lands at."""
    rungs = [
        Milestone("Survive & land one profitable test", 2_000,
                  "Get through the losing tests to a single product that's ROAS-positive "
                  "at small spend. This is mostly discipline, not luck.",
                  "~90% of new sellers quit before here; <10% survive year one. The "
                  "near-certain payoff of getting this far is the skill, not the cash."),
        Milestone("Scale the first winner", 10_000,
                  "One product held above break-even while you raise budget in ~20–30% "
                  "steps and diversify creative angles before fatigue hits.",
                  "The minority who get one real winner. Most never do — that's structural, "
                  "not a personal failing."),
        Milestone("Multi-product operator", 50_000,
                  "The top-seller pattern: 3+ viral products, 50+ active affiliates, "
                  "ROAS-positive paid on top. A portfolio, not a fluke.",
                  "Only ~1.5% of all stores ever cross $50k total. Real business now."),
        Milestone("Brand at scale", 150_000,
                  "Defensible aesthetic that photographs/unboxes well, repeat buyers "
                  "(TikTok Shop repeat rate is ~81%, ~5.3 orders/buyer/yr), margin that "
                  "absorbs a 10–20% affiliate cut without going underwater.",
                  "Approaching the top 1% of US sellers (~$215k/mo). Uncommon and durable."),
        Milestone("$1M/yr revenue run-rate", 83_333,
                  "$1,000,000 in a rolling 12 months = ~$83k/mo. A well-run brand milestone.",
                  "Hard but reached by the survivors who compound winners over 12–36 months."),
    ]
    rungs.sort(key=lambda m: m.monthly_revenue)
    # Flag the lowest rung the goal meets or exceeds (the nearest milestone at/above goal).
    flagged = False
    for m in rungs:
        if not flagged and monthly_rev_goal <= m.monthly_revenue:
            m.is_goal = True
            flagged = True
    if not flagged:  # goal is above every rung — flag the top one
        rungs[-1].is_goal = True
    return rungs


def plan_million(
    goal_amount: float = 1_000_000.0,
    goal_type: str = "revenue",
    horizon_months: int = 24,
    aov: float = AOV_DEFAULT,
    net_margin: float = BLENDED_MARGIN,
    pod_listings: int = 0,
) -> MillionDollarPlan:
    if goal_type not in ("revenue", "profit"):
        raise ValueError("goal_type must be 'revenue' or 'profit'")
    if goal_amount <= 0 or horizon_months <= 0:
        raise ValueError("goal_amount and horizon_months must be > 0")
    if aov <= 0:
        raise ValueError("aov must be > 0")
    if not 0 < net_margin <= 1:
        raise ValueError("net_margin must be a fraction in (0, 1]")

    # An optional Etsy POD stream chips away at the monthly target in parallel.
    pod_monthly = pod_listings * POD_REV_PER_LISTING_MO

    if goal_type == "profit":
        monthly_profit = goal_amount / horizon_months
        monthly_revenue = monthly_profit / net_margin
        cumulative_revenue = monthly_revenue * horizon_months
    else:  # revenue
        monthly_revenue = goal_amount / horizon_months
        monthly_profit = monthly_revenue * net_margin
        cumulative_revenue = goal_amount

    tt_monthly_revenue = max(0.0, monthly_revenue - pod_monthly)
    orders_per_day = tt_monthly_revenue / aov / 30.0
    units_per_day = orders_per_day  # ~1 unit/order at these AOVs unless you bundle
    winners_needed = max(1, math.ceil(tt_monthly_revenue / WINNER_CEILING_MO))
    monthly_ad_budget = tt_monthly_revenue * PAID_REVENUE_SHARE / TARGET_BLENDED_ROAS

    notes: list[str] = []
    if goal_type == "revenue":
        notes.append(f"at {net_margin*100:.0f}% net margin, ${goal_amount:,.0f} revenue "
                     f"≈ ${goal_amount*net_margin:,.0f} take-home — revenue is the easier "
                     "million; profit is the hard one.")
    else:
        organic_rev = goal_amount / ORGANIC_MARGIN
        notes.append(f"${goal_amount:,.0f} PROFIT needs ~${cumulative_revenue:,.0f} in "
                     "revenue at this margin — brand-at-scale territory. Going organic-first "
                     f"(~{ORGANIC_MARGIN*100:.0f}% margin) cuts that to ~${organic_rev:,.0f}: "
                     "making your own content instead of paying it out is the biggest lever "
                     "on the whole plan.")
    if pod_listings:
        notes.append(f"Etsy POD ({pod_listings} listings × ~${POD_REV_PER_LISTING_MO:.0f}/mo) "
                     f"contributes ~${pod_monthly:,.0f}/mo, leaving ~${tt_monthly_revenue:,.0f}"
                     "/mo for TikTok Shop to carry.")
    if winners_needed > 3:
        notes.append(f"{winners_needed} concurrent winners is a lot — one product ceilings "
                     f"around ~${WINNER_CEILING_MO:,.0f}/mo. A longer horizon or a higher "
                     "AOV (bundles) lowers how many you must run at once.")

    return MillionDollarPlan(
        goal_amount=goal_amount, goal_type=goal_type, horizon_months=horizon_months,
        aov=aov, net_margin=net_margin,
        monthly_revenue_needed=round(monthly_revenue, 2),
        monthly_profit_at_target=round(monthly_profit, 2),
        cumulative_revenue_needed=round(cumulative_revenue, 2),
        orders_per_day=round(orders_per_day, 1), units_per_day=round(units_per_day, 1),
        winners_needed=winners_needed, monthly_ad_budget=round(monthly_ad_budget, 2),
        percentile=_percentile(monthly_revenue), milestones=_milestones(monthly_revenue),
        notes=notes,
    )


# ── the $100k month, itemized ───────────────────────────────────────────────────
@dataclass
class ScalePlan:
    """What a target month actually costs to RUN — the working-capital and
    operating-cadence view the milestone ladder doesn't show. Revenue is vanity;
    this is the machine underneath it."""
    monthly_revenue: float
    aov: float
    net_margin: float
    monthly_profit: float
    orders_per_day: float
    winners_needed: int
    monthly_ad_budget: float
    affiliates_target: int
    videos_per_week: int
    cogs_float: float                 # COGS you front during the payout lag
    contingency: float
    working_capital: float            # ad budget + COGS float + contingency
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# The ${self.monthly_revenue:,.0f} month, itemized",
            "",
            f"  take-home at {self.net_margin*100:.0f}% blended net: "
            f"~${self.monthly_profit:,.0f}/mo",
            f"  volume: ~{self.orders_per_day:.0f} orders/day at ${self.aov:.0f} AOV",
            f"  portfolio: ~{self.winners_needed} concurrent winners "
            f"(one product ceilings ~${WINNER_CEILING_MO:,.0f}/mo — the engine's "
            "ceiling estimate exists to pick products that can stack this high)",
            f"  ads: ~${self.monthly_ad_budget:,.0f}/mo "
            f"(at {TARGET_BLENDED_ROAS:.1f}× blended ROAS, "
            f"{PAID_REVENUE_SHARE*100:.0f}% of revenue paid-driven)",
            f"  affiliates: ~{self.affiliates_target}+ active "
            "(the researched top-seller pattern: 3+ viral products, 50+ affiliates)",
            f"  creative: ~{self.videos_per_week} videos/week across the portfolio "
            "(Higgsfield batches + affiliate content; fatigue is the tax on scale)",
            "",
            "  WORKING CAPITAL TO RUN THIS MONTH:",
            f"    ad budget (fronted)          ${self.monthly_ad_budget:>10,.0f}",
            f"    COGS float (payout lag)      ${self.cogs_float:>10,.0f}",
            f"    contingency (15%)            ${self.contingency:>10,.0f}",
            f"    TOTAL                        ${self.working_capital:>10,.0f}",
            "",
        ]
        lines += [f"  • {n}" for n in self.notes]
        return "\n".join(lines) + "\n"


def plan_scale(
    monthly_revenue: float = 100_000.0,
    aov: float = AOV_DEFAULT,
    net_margin: float = BLENDED_MARGIN,
    cogs_share: float = 0.35,
) -> ScalePlan:
    """The operating model for a target month (default: the $100k month).

    plan_million answers "what does the GOAL take"; this answers "what does one
    such MONTH cost to run" — cash fronted, portfolio shape, content cadence."""
    if monthly_revenue <= 0 or aov <= 0:
        raise ValueError("monthly_revenue and aov must be > 0")
    if not 0 < net_margin <= 1:
        raise ValueError("net_margin must be a fraction in (0, 1]")
    if not 0 < cogs_share < 1:
        raise ValueError("cogs_share must be a fraction in (0, 1)")

    winners = max(1, math.ceil(monthly_revenue / WINNER_CEILING_MO))
    ad_budget = monthly_revenue * PAID_REVENUE_SHARE / TARGET_BLENDED_ROAS
    # You front COGS while TikTok holds payouts (~14 days) — imported from the
    # month-one calculator so the two cash models can never drift apart.
    from .capital.month_one import PAYOUT_LAG_DAYS
    cogs_float = monthly_revenue * cogs_share * (PAYOUT_LAG_DAYS / 30.0)
    contingency = 0.15 * (ad_budget + cogs_float)
    working = ad_budget + cogs_float + contingency

    notes = [
        "sequence matters: this is the month-N machine, not month one — survive "
        "the first profitable test, scale the first winner, THEN build the portfolio",
        f"the profit lever is margin, not volume: at organic-first "
        f"({ORGANIC_MARGIN*100:.0f}%) the same revenue takes home "
        f"~${monthly_revenue*ORGANIC_MARGIN:,.0f} instead of "
        f"~${monthly_revenue*net_margin:,.0f}",
        "product selection is the constraint: the EV queue + ceiling check exist "
        f"so the portfolio is {winners} products with ≥$25k ceilings, not ten "
        "products that ceiling at $8k",
    ]
    return ScalePlan(
        monthly_revenue=monthly_revenue, aov=aov, net_margin=net_margin,
        monthly_profit=round(monthly_revenue * net_margin, 2),
        orders_per_day=round(monthly_revenue / aov / 30.0, 1),
        winners_needed=winners, monthly_ad_budget=round(ad_budget, 2),
        affiliates_target=max(50, winners * 20),
        videos_per_week=winners * 10,
        cogs_float=round(cogs_float, 2), contingency=round(contingency, 2),
        working_capital=round(working, 2), notes=notes,
    )


SOURCES = (
    "https://greyjournal.net/hustle/tiktok-shop-seller-profit-margins-2026/",
    "https://www.fastmoss.com/blog/tiktok-shop-profitability-q1-2026-top-10-us-sellers/",
    "https://branvas.com/blogs/news/tiktok-shop-statistics",
    "https://marketingltb.com/blog/statistics/tiktok-shop-statistics/",
    "https://redstagfulfillment.com/what-is-average-tiktok-shop-order-value/",
    "https://trueprofit.io/blog/dropshipping-success-rate",
    "https://branvas.com/blogs/news/is-dropshipping-profitable",
    "https://www.artomate.app/blog/etsy-print-on-demand-side-hustle-2026-earnings-how-to-start",
)


def render_roadmap(plan: MillionDollarPlan) -> str:
    out = ["# Road to $1M — the honest math", "", plan.summary, "",
           "## The odds, stated plainly", "",
           "- Over half of all TikTok Shops are inactive; fewer than 10% of new sellers "
           "survive year one.",
           "- Only ~1.5% of dropshipping stores ever earn more than $50k total; ~1–5% "
           "build a sustainable business.",
           "- The top 1% of US sellers drive ~60% of GMV; the median seller does "
           f"~${MEDIAN_SELLER_MO:,.0f}/mo. The distribution is brutally top-heavy.",
           "- This engine doesn't beat those odds by magic — it compresses time and "
           "enforces discipline (real landed cost, the 45% margin gate, the 48h kill "
           "timer, tuned scoring). The near-certain payoff is the skill and the system; "
           "the $1M is the low-probability upside on top. Build for the former.",
           "",
           f"## Sources (verified {VERIFIED_DATE})", ""]
    out += [f"- {u}" for u in SOURCES]
    return "\n".join(out) + "\n"
