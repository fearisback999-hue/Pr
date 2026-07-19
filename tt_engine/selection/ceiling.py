"""Revenue ceiling: can this product actually carry a big month?

Score answers "is this a good product?" — a quality question. A $100k month is also
a CAPACITY question: a $9 trinket selling 30 units/day market-wide can be flawless
and still never move the needle. This estimates a plausible monthly revenue ceiling
for YOU (a new entrant capturing a share of the observed market), then asks the
blunt question the board never asked: how many products like this would a $100k
month take?

Honesty rules carried over from the rest of the engine:
  • market size comes from the imported data, despiked — one viral day is content
    signal, not market size
  • capture share and headroom are STATED heuristics, not knowledge; they exist to
    rank products against each other, not to forecast your P&L
  • contribution uses the TRUE fee stack (referral + payment + affiliate), not the
    scorer's 6%-only comparability view — profit questions get profit math
  • no landed cost on file → no contribution estimate (the same refusal as
    everywhere else: numbers that gate real money are never guessed)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..db import models
from ..detection import LifecycleResult, TriggerResult
from ..detection._stats import clamp, despike
from ..economics import Economics
from ..economics.optimizer import DEFAULT_PAYMENT_RATE, true_economics

TARGET_MONTH = 100_000.0
# One product tends to ceiling around here before fatigue/saturation force the next
# (shared with the roadmap's researched planning heuristic, 2026-07-09).
WINNER_CEILING_MO = 40_000.0

# How much room the market itself has left, by lifecycle stage. Multiplies the
# observed run-rate: an early trend can still multiply; a peak can only decay.
HEADROOM = {
    "brand_new": 6.0,      # could run, but the estimate rests on thin data
    "early_trend": 5.0,
    "growing": 3.0,
    "peaking": 1.2,
    "oversaturated": 1.0,
    "dead": 0.0,
}

# Share of the observed market a new entrant plausibly captures: generous when the
# field is empty, brutal when it's crowded (25% at saturation 0 → 5% at 100).
def _capture_share(saturation_index: float) -> float:
    return clamp(0.25 - 0.20 * saturation_index / 100.0, 0.05, 0.25)


@dataclass
class CeilingEstimate:
    market_monthly: float             # observed market run-rate, despiked, $/mo
    capture_share: float              # heuristic share a new entrant can take
    headroom: float                   # lifecycle multiplier on that capture
    ceiling_monthly: float            # min(market × capture × headroom, winner ceiling)
    orders_per_day_at_ceiling: float
    contribution_monthly: Optional[float]   # ceiling × TRUE margin; None = unpriced
    true_margin: Optional[float]
    products_needed_for_100k: Optional[int] # ceil($100k / ceiling); None if ceiling ~0
    notes: list[str] = field(default_factory=list)

    @property
    def too_small_to_matter(self) -> bool:
        """Even at ceiling this product carries <10% of a $100k month — it can be a
        fine FIRST product (reps, cash flow) but it is not a scale pillar."""
        return self.ceiling_monthly < TARGET_MONTH / 10

    @property
    def summary(self) -> str:
        head = (f"ceiling ~${self.ceiling_monthly:,.0f}/mo "
                f"(market ${self.market_monthly:,.0f}/mo × {self.capture_share:.0%} "
                f"capture × {self.headroom:.1f}× headroom)")
        if self.contribution_monthly is not None:
            head += (f" · ~${self.contribution_monthly:,.0f}/mo contribution at the "
                     f"true stack")
        if self.products_needed_for_100k is not None:
            head += f" · ~{self.products_needed_for_100k} like it = a $100k month"
        return head


def estimate_ceiling(
    metrics: Sequence[models.DailyMetric],
    trigger: TriggerResult,
    lifecycle: LifecycleResult,
    economics: Economics,
    payment_rate: float = DEFAULT_PAYMENT_RATE,
    affiliate_rate: float = 0.15,
) -> CeilingEstimate:
    ordered = sorted(metrics, key=lambda m: m.date)
    recent = ordered[-14:]
    units = despike([float(m.units) for m in recent]) if recent else []
    price = ordered[-1].price if ordered else 0.0
    daily_units = (sum(units) / len(units)) if units else 0.0
    market_monthly = daily_units * price * 30.0

    capture = _capture_share(trigger.saturation.index)
    headroom = HEADROOM.get(lifecycle.stage, 1.0)
    ceiling = min(market_monthly * capture * headroom, WINNER_CEILING_MO)

    notes: list[str] = []
    contribution = margin = None
    if economics.landed_known:
        te = true_economics(economics.sell_price, economics.supplier_cost,
                            economics.ship_cost, payment_rate, affiliate_rate)
        margin = te.true_margin
        contribution = round(ceiling * max(te.true_margin, 0.0), 2)
        if te.true_margin <= 0:
            notes.append("true margin ≤ 0 at the full fee stack — the ceiling is "
                         "revenue you'd PAY to process")
    else:
        notes.append("no landed cost on file — contribution not estimated "
                     "(add a supplier quote; capacity without margin is noise)")

    needed = math.ceil(TARGET_MONTH / ceiling) if ceiling >= 1.0 else None
    if lifecycle.stage == "brand_new":
        notes.append("brand_new stage: the market estimate rests on thin history — "
                     "treat the ceiling as a sketch, not a plan")
    est = CeilingEstimate(
        market_monthly=round(market_monthly, 2), capture_share=round(capture, 3),
        headroom=headroom, ceiling_monthly=round(ceiling, 2),
        orders_per_day_at_ceiling=round(ceiling / price / 30.0, 1) if price else 0.0,
        contribution_monthly=contribution, true_margin=margin,
        products_needed_for_100k=needed, notes=notes,
    )
    if est.too_small_to_matter:
        est.notes.append(
            f"too small to be a scale pillar: even at ceiling it carries "
            f"<10% of a $100k month ({needed if needed else '∞'} products like it "
            "needed) — fine for reps, wrong for scale")
    return est
