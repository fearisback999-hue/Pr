"""Tiny stdlib stats helpers for the detection math. No numpy dependency."""

from __future__ import annotations

import math
from typing import Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def slope(ys: Sequence[float]) -> float:
    """Least-squares slope of ys against x = 0..n-1 (units of y per step)."""
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def pct_change(old: float, new: float) -> float:
    """Fractional change from old→new. Guards divide-by-zero."""
    if old == 0:
        return 0.0 if new == 0 else 1.0
    return (new - old) / old


def exp_growth_rate(series: Sequence[float]) -> float:
    """Estimate daily multiplicative growth rate r where value ≈ v0 * (1+r)^t.

    Fits a line to log(value) and converts back. Returns 0.0 when the series is too
    short, flat, or non-positive. Used to project how fast competition is entering.
    """
    pts = [v for v in series if v and v > 0]
    if len(pts) < 3:
        return 0.0
    logs = [math.log(v) for v in pts]
    m = slope(logs)  # per-step change in log-space
    try:
        return math.exp(m) - 1.0
    except OverflowError:
        return 0.0


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
