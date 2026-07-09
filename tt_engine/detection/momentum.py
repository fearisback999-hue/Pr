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
    velocity_7d: float       # mean units/day, last 7 days (single-spike days capped)
    velocity_30d: float      # mean units/day, last 30 days
    momentum_ratio: float    # velocity_7d / velocity_30d ; > 1 = accelerating
    wow_growth: float        # week-over-week unit growth (fraction, spike-capped)
    slope_recent: float      # units/day slope over last 7 days
    acceleration: float      # slope(last 7) − slope(prior 7) ; > 0 = bending up
    is_accelerating: bool
    consistency: float = 0.5  # 0..1 — steadiness of the last 14d around their trend
    spike_capped: bool = False  # a single anomalous day was capped in the 7d window

    @property
    def summary(self) -> str:
        return (
            f"7d {self.velocity_7d:.0f}/day vs 30d {self.velocity_30d:.0f}/day "
            f"(x{self.momentum_ratio:.2f}), WoW {self.wow_growth*100:+.0f}%, "
            f"{'accelerating' if self.is_accelerating else 'flat/decel'}"
            + (", consistency %.2f" % self.consistency)
            + (" [spike capped]" if self.spike_capped else "")
        )


def _window(units: Sequence[int], days: int) -> list[int]:
    return list(units[-days:]) if len(units) >= days else list(units)


def compute_momentum(metrics: Sequence[models.DailyMetric]) -> MomentumResult:
    """Metrics must be sorted ascending by date (oldest → newest).

    Two robustness rules (accuracy over optimism):
      • A SINGLE anomalous day in a 7-day window is capped at 3× the window median
        before velocity/WoW are computed — one viral video is content signal, not
        sustained demand. A genuine ramp (many rising days) is untouched.
      • `consistency` measures how steady the last 14 days are around their own trend;
        steady growth predicts a real wave far better than a spiky average.
    """
    units = [m.units for m in metrics]
    if not units:
        return MomentumResult(0, 0, 0, 0, 0, 0, False)

    last7_raw = _window(units, 7)
    last7 = _stats.despike(last7_raw)
    spike_capped = last7 != last7_raw
    last30 = _window(units, 30)
    velocity_7d = _stats.mean(last7)
    velocity_30d = _stats.mean(last30)
    momentum_ratio = velocity_7d / velocity_30d if velocity_30d else 0.0

    # Prior week, spike-capped the same way as the recent week — so an OLD viral day
    # (8–14 days ago) can't inflate the baseline and understate this week's growth.
    # Both WoW growth and the acceleration slope reuse it, for a consistent comparison.
    prior7 = _stats.despike(units[-14:-7]) if len(units) >= 14 else []
    wow_growth = _stats.pct_change(sum(prior7), sum(last7)) if prior7 else 0.0

    slope_recent = _stats.slope(last7)
    # Acceleration: is the recent slope steeper than the prior week's slope?
    slope_prior = _stats.slope(prior7) if prior7 else 0.0
    acceleration = slope_recent - slope_prior

    is_accelerating = momentum_ratio > 1.05 and acceleration > 0
    return MomentumResult(
        velocity_7d=velocity_7d, velocity_30d=velocity_30d, momentum_ratio=momentum_ratio,
        wow_growth=wow_growth, slope_recent=slope_recent, acceleration=acceleration,
        is_accelerating=is_accelerating,
        consistency=_stats.trend_consistency(_window(units, 14)),
        spike_capped=spike_capped,
    )
