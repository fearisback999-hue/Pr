"""Product lifecycle stage — where in its life this product actually is.

Six stages, classified from the same real signals detection already computes (velocity,
acceleration, saturation level, entrant rate, ad age, history depth). The reasons are
returned with the verdict — no black-box labels.

  brand_new     — too little history to judge; watch, don't bet
  early_trend   — accelerating, competition still scarce → the window everyone hunts
  growing       — accelerating with competition arriving; act fast, runway is burning
  peaking       — growth stalled while entrants still pile in; late money buys the top
  oversaturated — crowded red ocean regardless of sales level (the commodity gate zone)
  dead          — demand declining; the wave already broke

The order of checks matters: crowding trumps momentum (a saturated product that still
grows is a fight you've already lost on CAC), and decline trumps everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ..db import models
from .trigger import TriggerResult

# Stage boundaries — heuristics on the same 0–100 saturation index and momentum ratios
# the rest of detection uses. Recalibrate against your own outcomes (Part 13).
MIN_HISTORY_DAYS = 14          # below this the honest answer is "too new to judge"
SAT_OVERSATURATED = 65.0       # matches the commodity hard gate
SAT_EARLY_MAX = 25.0           # under this, competition is genuinely scarce
DECLINE_RATIO = 0.85           # 7d velocity below 85% of 30d = demand rolling over
STALL_RATIO = 1.05             # under this, growth has stalled (matches is_accelerating)

STAGES = ("brand_new", "early_trend", "growing", "peaking", "oversaturated", "dead")


@dataclass
class LifecycleResult:
    stage: str                       # one of STAGES
    reasons: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"{self.stage.replace('_', ' ')}: " + "; ".join(self.reasons)

    @property
    def actionable(self) -> bool:
        """The two stages worth new money. Peaking/oversaturated/dead are entries you'd
        regret; brand_new is a watch, not a bet."""
        return self.stage in ("early_trend", "growing")


def classify_lifecycle(
    metrics: Sequence[models.DailyMetric], trigger: TriggerResult
) -> LifecycleResult:
    """Metrics must be sorted ascending by date (same contract as detection)."""
    m = trigger.momentum
    sat = trigger.saturation

    if len(metrics) < MIN_HISTORY_DAYS:
        return LifecycleResult("brand_new", [
            f"only {len(metrics)} day(s) of history (< {MIN_HISTORY_DAYS}) — too new to "
            "judge; keep logging before betting"
        ])

    # Decline first: a wave that broke is dead however crowded or empty the field is.
    # (WoW, not slope-acceleration: a declining exponential has a positive second
    # derivative, so 'acceleration' misleads here — week-over-week doesn't.)
    if m.momentum_ratio < DECLINE_RATIO and m.wow_growth <= 0:
        return LifecycleResult("dead", [
            f"7d velocity is {m.momentum_ratio:.2f}× the 30d baseline (< {DECLINE_RATIO}) "
            f"with WoW {m.wow_growth*100:+.0f}% — demand is rolling over",
            f"saturation {sat.index:.0f}/100 with entrant rate "
            f"{sat.entrant_rate*100:+.1f}%/day — whoever is still entering is buying the top",
        ])

    # Crowding second: momentum can't rescue a red ocean (CAC is set by the crowd).
    if sat.index >= SAT_OVERSATURATED:
        return LifecycleResult("oversaturated", [
            f"saturation {sat.index:.0f}/100 ≥ {SAT_OVERSATURATED:.0f} — "
            f"{sat.sellers} sellers, {sat.promo_videos} promo videos, {sat.ads} ads",
            "matches the commodity hard gate: entering now means outbidding the crowd "
            "for the same customer",
        ])

    accelerating = m.is_accelerating and m.momentum_ratio >= STALL_RATIO

    if not accelerating:
        # Growth stalled but people are still piling in → the classic top.
        return LifecycleResult("peaking", [
            f"growth stalled (7d/30d ratio {m.momentum_ratio:.2f}, acceleration "
            f"{m.acceleration:+.1f}) while entrant rate is {sat.entrant_rate*100:+.1f}%/day",
            f"saturation {sat.index:.0f}/100 and rising — late entrants fund the peak, "
            "they don't ride it",
        ])

    if sat.index < SAT_EARLY_MAX:
        return LifecycleResult("early_trend", [
            f"accelerating ({m.momentum_ratio:.2f}× baseline, WoW {m.wow_growth*100:+.0f}%) "
            f"with competition still scarce (saturation {sat.index:.0f}/100 "
            f"< {SAT_EARLY_MAX:.0f})",
            f"~{trigger.window_days:.0f} days of runway before the field crowds — this is "
            "the window the whole engine exists to catch",
        ])

    return LifecycleResult("growing", [
        f"accelerating ({m.momentum_ratio:.2f}× baseline, WoW {m.wow_growth*100:+.0f}%) "
        f"but competition is arriving (saturation {sat.index:.0f}/100, entrant rate "
        f"{sat.entrant_rate*100:+.1f}%/day)",
        f"~{trigger.window_days:.0f} days of runway — act fast; every week of delay is "
        "margin handed to the entrants",
    ])
