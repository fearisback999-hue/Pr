"""Cash-flow tracking: payout float, runway, and how many tests the capital supports.

The model is deliberately conservative (it ignores incoming revenue when sizing runway),
because the whole point of Part 11 is surviving the losing tests and floating the payout
gap — not projecting profit. It outputs numbers and warnings; you make the call."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_PAYOUT_LAG_DAYS = 14.0   # TikTok typically holds payouts ~7–15 days
RESERVE_FRACTION = 0.15          # keep a buffer; don't deploy 100% of capital
MIN_CONCURRENT_TESTS = 3         # below this you can't absorb the losers that pay for a winner


@dataclass
class CashFlowPlan:
    capital: float
    test_budget: float           # cost to test one product (creative + ad spend)
    payout_lag_days: float
    daily_ad_spend: float
    daily_cogs: float            # daily cost of goods you front before payout
    monthly_fixed: float
    payout_float: float          # cash tied up waiting for held payouts
    reserve: float               # buffer held back
    deployable: float            # capital − float − reserve
    max_concurrent_tests: int
    monthly_burn: float          # gross monthly outflow (no revenue assumed)
    runway_months: float
    undercapitalized: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        runway = "∞" if self.runway_months == float("inf") else f"{self.runway_months:.1f}mo"
        head = (
            f"capital ${self.capital:,.0f} · payout float ${self.payout_float:,.0f} · "
            f"deployable ${self.deployable:,.0f} · {self.max_concurrent_tests} concurrent tests · "
            f"runway {runway}"
        )
        if self.warnings:
            head += "\n  ⚠️ " + "\n  ⚠️ ".join(self.warnings)
        return head


def plan_capital(
    capital: float,
    test_budget: float,
    payout_lag_days: float = DEFAULT_PAYOUT_LAG_DAYS,
    daily_ad_spend: float = 0.0,
    daily_cogs: float = 0.0,
    monthly_fixed: float = 0.0,
) -> CashFlowPlan:
    # Cash you can't touch because it's in transit waiting for TikTok to pay out.
    payout_float = max(0.0, (daily_ad_spend + daily_cogs) * payout_lag_days)
    reserve = max(0.0, capital) * RESERVE_FRACTION
    deployable = max(0.0, capital - payout_float - reserve)
    max_tests = int(deployable // test_budget) if test_budget > 0 else 0

    monthly_burn = monthly_fixed + (daily_ad_spend + daily_cogs) * 30.0
    runway_months = capital / monthly_burn if monthly_burn > 0 else float("inf")

    warnings: list[str] = []
    undercap = False
    if max_tests < MIN_CONCURRENT_TESTS:
        warnings.append(
            f"capital supports {max_tests} concurrent test(s) (< {MIN_CONCURRENT_TESTS}); "
            "too thin to absorb the losing tests that pay for a winner"
        )
        undercap = True
    if runway_months < 3:
        warnings.append(
            f"runway {runway_months:.1f} months — most tests lose before one works; "
            "you may run out before finding a winner"
        )
        undercap = True
    if capital > 0 and payout_float > capital * 0.5:
        warnings.append(
            "payout float ties up >50% of capital — the payout lag will choke cash flow"
        )
        undercap = True

    return CashFlowPlan(
        capital=capital, test_budget=test_budget, payout_lag_days=payout_lag_days,
        daily_ad_spend=daily_ad_spend, daily_cogs=daily_cogs, monthly_fixed=monthly_fixed,
        payout_float=round(payout_float, 2), reserve=round(reserve, 2),
        deployable=round(deployable, 2), max_concurrent_tests=max_tests,
        monthly_burn=round(monthly_burn, 2), runway_months=runway_months,
        undercapitalized=undercap, warnings=warnings,
    )
