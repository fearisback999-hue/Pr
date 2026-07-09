"""Etsy print-on-demand listing planner — how many listings to publish, and at what
weekly cadence, to hit a profit target. All math shown; every assumption is a knob.

The honest model: POD is a volume game. A new-shop listing typically converts to
~0.2–0.5 sales/month (search-dependent); an established shop with reviews sees ~1–2.
Nobody knows your niche's true rate until you have data — start with the conservative
default, then re-plan with YOUR observed sales-per-listing once ~30 days of data exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Conservative default for a new shop without reviews. Replace with your measured
# rate (total monthly sales ÷ live listings) as soon as you have one.
DEFAULT_SALES_PER_LISTING_MONTH = 0.3


@dataclass
class PodPlan:
    target_monthly_profit: float
    profit_per_sale: float
    sales_per_listing_month: float
    current_listings: int
    hours_per_week: float
    minutes_per_listing: float
    # Derived (all shown):
    sales_needed_month: float
    listings_needed: int
    new_listings_needed: int
    weekly_capacity: int          # how many listings your hours allow per week
    weekly_recommended: int       # min(capacity, an 8-week ramp pace)
    weeks_to_target: float

    @property
    def summary(self) -> str:
        lines = [
            f"target ${self.target_monthly_profit:,.0f}/mo ÷ ${self.profit_per_sale:.2f} "
            f"profit/sale = {self.sales_needed_month:,.0f} sales/mo",
            f"{self.sales_needed_month:,.0f} sales/mo ÷ {self.sales_per_listing_month:.2f} "
            f"sales/listing/mo = {self.listings_needed:,} listing(s) needed "
            f"({self.new_listings_needed:,} more than the {self.current_listings:,} live now)",
            f"your time: {self.hours_per_week:.1f} h/wk ÷ {self.minutes_per_listing:.0f} "
            f"min/listing = {self.weekly_capacity} listing(s)/week possible",
            f"→ publish {self.weekly_recommended}/week · target reached in "
            f"~{self.weeks_to_target:.0f} week(s)",
        ]
        if self.weekly_capacity < self.weekly_recommended:
            lines.append("⚠ time-capped: your hours are the constraint, not the plan")
        lines.append("Re-plan with your MEASURED sales/listing after ~30 days of data — "
                     f"the {self.sales_per_listing_month:.2f} default is a cold-start guess.")
        return "\n".join(lines)


def plan_pod(
    target_monthly_profit: float,
    profit_per_sale: float,
    sales_per_listing_month: float = DEFAULT_SALES_PER_LISTING_MONTH,
    current_listings: int = 0,
    hours_per_week: float = 5.0,
    minutes_per_listing: float = 30.0,
    ramp_weeks: int = 8,
) -> PodPlan:
    if profit_per_sale <= 0:
        raise ValueError("profit_per_sale must be > 0 — compute it first "
                         "(sale price − POD base cost − Etsy fees ~9.5% − ads)")
    if sales_per_listing_month <= 0:
        raise ValueError("sales_per_listing_month must be > 0")
    if minutes_per_listing <= 0:
        raise ValueError("minutes_per_listing must be > 0")

    sales_needed = target_monthly_profit / profit_per_sale
    listings_needed = math.ceil(sales_needed / sales_per_listing_month)
    new_needed = max(0, listings_needed - current_listings)
    weekly_capacity = max(1, int(hours_per_week * 60 // minutes_per_listing))
    ramp_pace = max(1, math.ceil(new_needed / ramp_weeks)) if new_needed else 0
    weekly_recommended = min(weekly_capacity, ramp_pace) if new_needed else 0
    weeks = (new_needed / weekly_recommended) if weekly_recommended else 0.0

    return PodPlan(
        target_monthly_profit=target_monthly_profit, profit_per_sale=profit_per_sale,
        sales_per_listing_month=sales_per_listing_month, current_listings=current_listings,
        hours_per_week=hours_per_week, minutes_per_listing=minutes_per_listing,
        sales_needed_month=sales_needed, listings_needed=listings_needed,
        new_listings_needed=new_needed, weekly_capacity=weekly_capacity,
        weekly_recommended=weekly_recommended, weeks_to_target=weeks,
    )
