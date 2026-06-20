"""Saturation index = how crowded the opportunity already is, and how fast it's
crowding. A flood of brand-new ads means others just entered and the window is closing.

Higher index = more saturated (worse). We track both the absolute level and the
*entrant rate* (how fast sellers / promo videos / ads are growing), because the timing
edge is "low-but-rising", not "zero".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..db import models
from . import _stats

# Reference ceilings at which each driver is considered "crowded". Heuristics — tune
# per category and recalibrate against your own results (Part 13).
CROWDED_SELLERS = 60
CROWDED_PROMO = 100
CROWDED_ADS = 50
FRESH_AD_AGE_DAYS = 10  # below this, ads are fresh → new entrants flooding in


@dataclass
class SaturationResult:
    sellers: int
    promo_videos: int
    ads: int
    avg_ad_age: float
    index: float           # 0..100, higher = more crowded
    entrant_rate: float    # daily multiplicative growth of competition
    fresh_ads: bool        # ads are young AND ad count rising → window closing
    rising: bool           # competition is increasing but not yet crowded

    @property
    def summary(self) -> str:
        return (
            f"sat {self.index:.0f}/100 ({self.sellers} sellers, {self.promo_videos} promos, "
            f"{self.ads} ads, ad-age {self.avg_ad_age:.0f}d), "
            f"entrant rate {self.entrant_rate*100:+.0f}%/day"
        )


def compute_saturation(metrics: Sequence[models.DailyMetric]) -> SaturationResult:
    """Metrics must be sorted ascending by date."""
    if not metrics:
        return SaturationResult(0, 0, 0, 0.0, 0.0, 0.0, False, False)

    latest = metrics[-1]
    # Absolute crowding: how far each driver is toward its "crowded" ceiling.
    seller_load = _stats.clamp(latest.sellers / CROWDED_SELLERS, 0, 1)
    promo_load = _stats.clamp(latest.promo_videos / CROWDED_PROMO, 0, 1)
    ad_load = _stats.clamp(latest.ads / CROWDED_ADS, 0, 1)
    # Old ads soften the index slightly (entrenched, slow market); fresh ads keep it sharp.
    age_factor = _stats.clamp(latest.avg_ad_age / 60, 0, 1)
    index = 100 * (0.4 * seller_load + 0.35 * promo_load + 0.25 * ad_load)
    # Down-weight a touch when ads are very old (market is mature but not actively flooding).
    index *= (0.85 + 0.15 * (1 - age_factor)) if latest.avg_ad_age > FRESH_AD_AGE_DAYS else 1.0

    # Entrant rate: how fast competition is growing (avg of the three drivers' growth).
    rates = [
        _stats.exp_growth_rate([m.sellers for m in metrics]),
        _stats.exp_growth_rate([m.promo_videos for m in metrics]),
        _stats.exp_growth_rate([m.ads for m in metrics]),
    ]
    entrant_rate = _stats.mean(rates)

    fresh_ads = latest.avg_ad_age < FRESH_AD_AGE_DAYS and rates[2] > 0.01
    rising = entrant_rate > 0.01 and index < 60

    return SaturationResult(
        sellers=latest.sellers, promo_videos=latest.promo_videos, ads=latest.ads,
        avg_ad_age=latest.avg_ad_age, index=round(index, 1), entrant_rate=entrant_rate,
        fresh_ads=fresh_ads, rising=rising,
    )
