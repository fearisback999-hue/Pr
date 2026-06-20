"""The trigger: high momentum AND low-but-rising saturation.

Always outputs a window estimate — days until the niche is crowded, projected from the
rate new sellers and ads are entering. "Good product, ~18 days of runway" is the useful
form (Part 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..db import models
from . import _stats
from .momentum import MomentumResult, compute_momentum
from .saturation import (
    CROWDED_ADS,
    CROWDED_PROMO,
    CROWDED_SELLERS,
    SaturationResult,
    compute_saturation,
)

# Trigger thresholds (Part 9 calls these starting heuristics — recalibrate in Part 13).
MOMENTUM_RATIO_MIN = 1.10      # 7d velocity at least 10% above the 30d baseline
WOW_GROWTH_MIN = 0.20         # strong week-over-week growth
SATURATION_INDEX_MAX = 55.0   # still room — not yet crowded
MAX_WINDOW_DAYS = 90.0        # cap the runway estimate


@dataclass
class TriggerResult:
    triggered: bool
    momentum: MomentumResult
    saturation: SaturationResult
    window_days: float
    reasons: list[str]

    @property
    def headline(self) -> str:
        verb = "TRIGGER" if self.triggered else "no-go"
        return (f"[{verb}] ~{self.window_days:.0f}d runway · "
                f"{self.momentum.summary} · {self.saturation.summary}")


def _days_to_ceiling(current: float, ceiling: float, daily_rate: float) -> float:
    """Days for `current` to reach `ceiling` growing at multiplicative `daily_rate`."""
    if current >= ceiling:
        return 0.0
    if daily_rate <= 0:
        return MAX_WINDOW_DAYS  # not growing → effectively open-ended (capped)
    days = math.log(ceiling / max(current, 1e-9)) / math.log(1 + daily_rate)
    return _stats.clamp(days, 0.0, MAX_WINDOW_DAYS)


def estimate_window(metrics: Sequence[models.DailyMetric], sat: SaturationResult) -> float:
    """Runway = whichever competition driver crowds first."""
    if not metrics:
        return 0.0
    latest = metrics[-1]
    rate_sellers = _stats.exp_growth_rate([m.sellers for m in metrics])
    rate_promo = _stats.exp_growth_rate([m.promo_videos for m in metrics])
    rate_ads = _stats.exp_growth_rate([m.ads for m in metrics])
    candidates = [
        _days_to_ceiling(latest.sellers, CROWDED_SELLERS, rate_sellers),
        _days_to_ceiling(latest.promo_videos, CROWDED_PROMO, rate_promo),
        _days_to_ceiling(latest.ads, CROWDED_ADS, rate_ads),
    ]
    window = min(candidates)
    # Fresh-ad flood is a hard tell the window is closing — haircut the estimate.
    if sat.fresh_ads:
        window *= 0.6
    return round(_stats.clamp(window, 0.0, MAX_WINDOW_DAYS), 1)


def evaluate(metrics: Sequence[models.DailyMetric]) -> TriggerResult:
    """Run the full detection pass over one product's daily series."""
    metrics = sorted(metrics, key=lambda m: m.date)
    momentum = compute_momentum(metrics)
    saturation = compute_saturation(metrics)
    window = estimate_window(metrics, saturation)

    reasons: list[str] = []
    high_momentum = (
        momentum.momentum_ratio >= MOMENTUM_RATIO_MIN
        and momentum.wow_growth >= WOW_GROWTH_MIN
        and momentum.is_accelerating
    )
    low_saturation = saturation.index <= SATURATION_INDEX_MAX

    if momentum.momentum_ratio < MOMENTUM_RATIO_MIN:
        reasons.append(f"momentum ratio {momentum.momentum_ratio:.2f} < {MOMENTUM_RATIO_MIN}")
    if momentum.wow_growth < WOW_GROWTH_MIN:
        reasons.append(f"WoW growth {momentum.wow_growth*100:.0f}% < {WOW_GROWTH_MIN*100:.0f}%")
    if not momentum.is_accelerating:
        reasons.append("sales not accelerating (flat or peaked)")
    if saturation.index > SATURATION_INDEX_MAX:
        reasons.append(f"already crowded (saturation {saturation.index:.0f} > {SATURATION_INDEX_MAX:.0f})")

    triggered = high_momentum and low_saturation
    if triggered:
        reasons = [
            f"momentum x{momentum.momentum_ratio:.2f}, WoW {momentum.wow_growth*100:+.0f}%, "
            f"accelerating; saturation {saturation.index:.0f} with room; ~{window:.0f}d runway"
        ]
    return TriggerResult(
        triggered=triggered, momentum=momentum, saturation=saturation,
        window_days=window, reasons=reasons,
    )
