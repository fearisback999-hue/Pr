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


def median(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def despike(xs: Sequence[float], factor: float = 3.0) -> list[float]:
    """Cap a SINGLE anomalous day at factor × the median of the window.

    One viral video makes one huge day; it is signal about content, not about
    sustained demand. Only the max is capped, and only when it's an outlier —
    a genuinely ramping series (many rising days) passes through untouched."""
    if len(xs) < 4:
        return list(xs)
    med = median(xs)
    if med <= 0:
        return list(xs)
    cap = factor * med
    peak = max(xs)
    if peak <= cap:
        return list(xs)
    return [min(x, cap) for x in xs]


def trend_consistency(xs: Sequence[float]) -> float:
    """How steady the series is around its own linear trend, in 0..1.

    1.0 = clean ramp (residuals tiny vs the level), → 0 = noise/spikes dominate.
    Computed as 1 − clamp(RMS(residuals) / mean, 0, 1). Steady multi-day growth
    is far more predictive of a real product wave than one spiky day."""
    n = len(xs)
    if n < 4:
        return 0.5  # not enough history to judge — neutral
    m = mean(xs)
    if m <= 0:
        return 0.0
    b = slope(xs)
    a = m - b * (n - 1) / 2  # intercept of the least-squares line
    resid = [x - (a + b * i) for i, x in enumerate(xs)]
    rms = math.sqrt(sum(r * r for r in resid) / n)
    return clamp(1.0 - rms / m, 0.0, 1.0)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
