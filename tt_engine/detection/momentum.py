"""Momentum = the slope and acceleration of sales.

The signal is not "sells a lot" — it's "bending upward". We compare recent velocity to
the trailing baseline and measure whether the slope itself is increasing (acceleration).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..db import models
from . import _stats


@dataclass
class MomentumResult:
    velocity_7d: float       # mean units/day, last 7 days
    velocity_30d: float      # mean units/day, last 30 days
    momentum_ratio: float    # velocity_7d / velocity_30d ; > 1 = accelerating
    wow_growth: float        # week-over-week unit growth (fraction)
    slope_recent: float      # units/day slope over last 7 days
    acceleration: float      # slope(last 7) − slope(prior 7) ; > 0 = bending up
    is_accelerating: bool

    @property
    def summary(self) -> str:
        return (
            f"7d {self.velocity_7d:.0f}/day vs 30d {self.velocity_30d:.0f}/day "
            f"(x{self.momentum_ratio:.2f}), WoW {self.wow_growth*100:+.0f}%, "
            f"{'accelerating' if self.is_accelerating else 'flat/decel'}"
        )


def _window(units: Sequence[int], days: int) -> list[int]:
    return list(units[-days:]) if len(units) >= days else list(units)


def compute_momentum(metrics: Sequence[models.DailyMetric]) -> MomentumResult:
    """Metrics must be sorted ascending by date (oldest → newest)."""
    units = [m.units for m in metrics]
    if not units:
        return MomentumResult(0, 0, 0, 0, 0, 0, False)

    last7 = _window(units, 7)
    last30 = _window(units, 30)
    velocity_7d = _stats.mean(last7)
    velocity_30d = _stats.mean(last30)
    momentum_ratio = velocity_7d / velocity_30d if velocity_30d else 0.0

    # Week-over-week: last 7 days vs the 7 before them.
    if len(units) >= 14:
        prior7 = units[-14:-7]
        wow_growth = _stats.pct_change(sum(prior7), sum(last7))
    else:
        wow_growth = 0.0

    slope_recent = _stats.slope(last7)
    # Acceleration: is the recent slope steeper than the prior week's slope?
    if len(units) >= 14:
        slope_prior = _stats.slope(units[-14:-7])
    else:
        slope_prior = 0.0
    acceleration = slope_recent - slope_prior

    is_accelerating = momentum_ratio > 1.05 and acceleration > 0
    return MomentumResult(
        velocity_7d=velocity_7d, velocity_30d=velocity_30d, momentum_ratio=momentum_ratio,
        wow_growth=wow_growth, slope_recent=slope_recent, acceleration=acceleration,
        is_accelerating=is_accelerating,
    )
