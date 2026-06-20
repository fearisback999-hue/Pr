"""A deterministic synthetic feed so the whole engine runs offline end-to-end.

It hand-builds a spread of archetypes that exercise every branch of detection,
scoring, and the hard gates:

  • rising_star   — sales bending upward, saturation still low, fresh ads → should TRIGGER
  • early_breakout— steep week-over-week growth, almost no competition yet → strong TRIGGER
  • peaked        — high sales but flat/declining, crowded, stale ads → must NOT trigger
                    (Appendix B's #1 beginner mistake: chasing products that already peaked)
  • dud           — flat low sales, nothing happening
  • thin_margin   — momentum looks fine but economics fail the margin hard gate
  • branded       — trademarked item → hard-gate disqualified regardless of momentum
  • restricted    — restricted TikTok category → hard-gate disqualified

The numbers are illustrative, not real market data. Replace with a live adapter.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from ..db import models
from .base import DataFeed, FeedRecord


@dataclass
class _Archetype:
    pid: str
    name: str
    category: str
    base_units: float          # day-0 daily units
    early_growth: float        # daily growth rate over the first 2/3 of the window
    late_growth: float         # daily growth rate over the final 1/3 (accel if > early)
    start_sellers: int
    seller_growth: float       # daily multiplicative growth of competition
    start_promo: int
    promo_growth: float
    start_ads: int
    ad_growth: float
    avg_ad_age_today: float    # low = fresh entrants flooding in (window closing)
    price: float
    branded: bool = False
    restricted: bool = False
    reviews: tuple[str, ...] = ()


_ARCHETYPES: list[_Archetype] = [
    _Archetype(
        pid="P-SCALPMASSAGER", name="Scalp Massager Pro", category="beauty",
        base_units=40, early_growth=0.03, late_growth=0.14,
        start_sellers=3, seller_growth=0.02, start_promo=4, promo_growth=0.04,
        start_ads=2, ad_growth=0.05, avg_ad_age_today=6, price=24.99,
        reviews=(
            "OMG this melts my tension headaches away after work, I use it every night",
            "bought it for stress and now my whole family fights over it",
            "the tingles are insane, so relaxing, cannot believe how good it feels",
            "helps me fall asleep, genuinely. wish I found it sooner",
            "shipping was fast and it actually works, not a gimmick",
        ),
    ),
    _Archetype(
        pid="P-LEDHOODIE", name="LED Light-Up Hoodie", category="apparel",
        base_units=20, early_growth=0.02, late_growth=0.20,
        start_sellers=2, seller_growth=0.015, start_promo=2, promo_growth=0.03,
        start_ads=1, ad_growth=0.04, avg_ad_age_today=4, price=39.99,
        reviews=(
            "wore this to a concert and everyone asked where I got it",
            "the glow is way brighter than I expected, total head-turner",
            "perfect for raves, festival season is gonna be crazy",
        ),
    ),
    _Archetype(
        pid="P-POSTURECORR", name="Posture Corrector Belt", category="wellness",
        base_units=300, early_growth=0.00, late_growth=-0.02,
        start_sellers=40, seller_growth=0.05, start_promo=120, promo_growth=0.06,
        start_ads=60, ad_growth=0.05, avg_ad_age_today=55, price=21.99,
        reviews=(
            "does what it says but everyone and their mom is selling this now",
            "okay product, returned one because sizing was off",
            "saw it on like 10 different shops, prices all over the place",
        ),
    ),
    _Archetype(
        pid="P-PHONESTAND", name="Generic Phone Stand", category="electronics",
        base_units=12, early_growth=0.005, late_growth=0.004,
        start_sellers=80, seller_growth=0.0, start_promo=30, promo_growth=0.0,
        start_ads=10, ad_growth=0.0, avg_ad_age_today=90, price=8.99,
        reviews=("it's a phone stand. it holds my phone.",),
    ),
    _Archetype(
        pid="P-CHEAPCABLE", name="Bargain USB Cable 3-pack", category="electronics",
        base_units=60, early_growth=0.02, late_growth=0.12,
        start_sellers=5, seller_growth=0.02, start_promo=3, promo_growth=0.03,
        start_ads=2, ad_growth=0.04, avg_ad_age_today=7, price=6.49,
        reviews=("works fine", "cheap and cheerful", "one stopped working after a month"),
    ),
    _Archetype(
        pid="P-BRANDPLUSH", name="Stitch Plush (licensed)", category="toys",
        base_units=90, early_growth=0.03, late_growth=0.16,
        start_sellers=6, seller_growth=0.02, start_promo=5, promo_growth=0.04,
        start_ads=3, ad_growth=0.05, avg_ad_age_today=5, price=27.99, branded=True,
        reviews=("my kid loves it", "so cute and soft", "the licensed ones are the best"),
    ),
    _Archetype(
        pid="P-VAPEKIT", name="Disposable Vape Kit", category="restricted",
        base_units=200, early_growth=0.04, late_growth=0.18,
        start_sellers=4, seller_growth=0.02, start_promo=3, promo_growth=0.03,
        start_ads=2, ad_growth=0.04, avg_ad_age_today=5, price=14.99, restricted=True,
        reviews=("great flavors",),
    ),
    _Archetype(
        pid="P-PIMPLEPATCH", name="Hydrocolloid Pimple Patches", category="beauty",
        base_units=80, early_growth=0.03, late_growth=0.15,
        start_sellers=4, seller_growth=0.02, start_promo=5, promo_growth=0.04,
        start_ads=3, ad_growth=0.05, avg_ad_age_today=6, price=16.99,
        reviews=(
            "these shrink my zits overnight, I'm obsessed",
            "cannot believe how fast they work, skin cleared up",
            "everyone asked what I did to my skin, amazing",
            "I keep reordering these, they actually melt the spot away",
        ),
    ),
    _Archetype(
        pid="P-MAGSPRAY", name="Magnesium Sleep Spray", category="wellness",
        base_units=50, early_growth=0.02, late_growth=0.15,
        start_sellers=3, seller_growth=0.02, start_promo=4, promo_growth=0.035,
        start_ads=2, ad_growth=0.045, avg_ad_age_today=7, price=22.99,
        reviews=(
            "I actually sleep through the night now, insane",
            "this knocked me out, so relaxing, wish I found it sooner",
            "spray it on and I'm out in minutes, reorder every month",
        ),
    ),
    _Archetype(
        pid="P-TRENDYTUMBLER", name="40oz Trendy Tumbler", category="home",
        base_units=400, early_growth=0.0, late_growth=-0.01,
        start_sellers=60, seller_growth=0.04, start_promo=200, promo_growth=0.05,
        start_ads=90, ad_growth=0.04, avg_ad_age_today=50, price=34.99,
        reviews=(
            "cute but literally everyone has one now",
            "saw it on every single shop, prices all over",
            "it's fine, holds drinks, nothing special anymore",
        ),
    ),
]


class MockFeed(DataFeed):
    name = "mock"

    def __init__(self, seed: int = 7):
        self._rng = random.Random(seed)

    def fetch(self, lookback_days: int = 35, limit: Optional[int] = None) -> list[FeedRecord]:
        today = date.today()
        records: list[FeedRecord] = []
        archetypes = _ARCHETYPES[:limit] if limit else _ARCHETYPES
        for a in archetypes:
            product = models.Product(
                id=a.pid, name=a.name, category=a.category,
                supplier_ref=f"SUP-{a.pid}", first_seen=(today - timedelta(days=lookback_days)).isoformat(),
                branded=a.branded, restricted=a.restricted,
            )
            metrics = self._series(a, lookback_days, today)
            records.append(FeedRecord(product=product, metrics=metrics, reviews=list(a.reviews)))
        return records

    def _series(self, a: _Archetype, n: int, today: date) -> list[models.DailyMetric]:
        out: list[models.DailyMetric] = []
        switch = int(n * 2 / 3)  # where late-stage growth kicks in
        units = a.base_units
        sellers = float(a.start_sellers)
        promo = float(a.start_promo)
        ads = float(a.start_ads)
        for i in range(n):
            day = today - timedelta(days=(n - 1 - i))
            g = a.early_growth if i < switch else a.late_growth
            units *= (1 + g)
            sellers *= (1 + a.seller_growth)
            promo *= (1 + a.promo_growth)
            ads *= (1 + a.ad_growth)
            # light deterministic noise so slopes aren't artificially perfect
            noise = 1 + self._rng.uniform(-0.05, 0.05)
            u = max(0, int(round(units * noise)))
            # ad age decays toward avg_ad_age_today as fresh ads enter
            age = a.avg_ad_age_today + (n - 1 - i) * 0.6
            out.append(models.DailyMetric(
                product_id=a.pid, date=day.isoformat(), units=u,
                gmv=round(u * a.price, 2), price=a.price,
                sellers=int(round(sellers)), promo_videos=int(round(promo)),
                ads=int(round(ads)), avg_ad_age=round(age, 1),
            ))
        return out
