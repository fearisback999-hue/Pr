"""Part 11 — Capital & Cash Flow. Ads cost money, inventory costs money, and most product
tests lose money before one works. On top of that TikTok HOLDS payouts, so there's a lag
between paying your supplier and getting paid by customers. Undercapitalized operators
with great execution still die here.

This module TRACKS the math — payout float, runway, how many tests you can afford. It
never makes the spending decision; that stays human (Part 12: never automate the spend)."""

from .cashflow import (
    DEFAULT_PAYOUT_LAG_DAYS,
    MIN_CONCURRENT_TESTS,
    RESERVE_FRACTION,
    CashFlowPlan,
    plan_capital,
)

__all__ = [
    "CashFlowPlan", "plan_capital", "DEFAULT_PAYOUT_LAG_DAYS",
    "RESERVE_FRACTION", "MIN_CONCURRENT_TESTS",
]
