"""Part 9 — 30-Day Validation Framework. Watch leading indicators in order:
3-second view rate → CTR → add-to-cart → ROAS. Then cut losers and pour into winners.
Thresholds are starting heuristics; calibrate them with your own results (Part 13)."""

from .framework import (
    KILL_CTR,
    KILL_HOURS,
    KILL_REFUND,
    SCALE_CTR,
    WEEK_PLAN,
    TestSummary,
    ValidationDecision,
    decide,
    hours_below_breakeven,
    summarize_tests,
)

__all__ = [
    "ValidationDecision", "TestSummary", "summarize_tests", "decide",
    "hours_below_breakeven", "WEEK_PLAN", "KILL_CTR", "SCALE_CTR", "KILL_REFUND",
    "KILL_HOURS",
]
