"""A deterministic synthetic feed so the whole engine runs offline end-to-end.

The archetypes are chosen to make one thing obvious: the engine surfaces DEFENSIBLE
NICHE products and rejects generic commodities. Generic me-too products (pimple patches,
tumblers, phone stands) don't work — competition floods in instantly and there's no edge
— so here they are the ones that get GATED or scored down, while the winners are
harder-to-copy niche finds with real runway.

  Niche winners (should be ATTACK-ready — low saturation, differentiated, healthy margin):
  • cowhide guitar strap   — musician + aesthetic niche, hard to commoditize
  • dog calming vest        — problem-specific pet niche (thunderstorm anxiety)
  • sourdough scoring lame  — hobby-baking niche, identity-driven

  Commodity traps (should be rejected — the point of the whole exercise):
  • pimple patches, 40oz tumbler, posture corrector — already crowded → COMMODITY gate
  • generic phone stand, bargain USB cable          — commodity + thin margin gate

  Compliance demos:
  • licensed plush → branded gate · disposable vape → restricted gate

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
    # ── NICHE WINNERS — defensible, low-competition, healthy margin → ATTACK ─────
    _Archetype(
        pid="P-COWHIDESTRAP", name="Cowhide Guitar Strap", category="accessories",
        base_units=75, early_growth=0.03, late_growth=0.19,
        start_sellers=3, seller_growth=0.015, start_promo=3, promo_growth=0.03,
        start_ads=2, ad_growth=0.04, avg_ad_age_today=5, price=39.99,
        reviews=(
            "I am OBSESSED, played my first open mic and everyone asked where I got it!",
            "the cowhide is real and no two are the same, mine is gorgeous, I love it",
            "cannot believe how much nicer this is than the generic nylon straps",
            "bought it for my guitarist boyfriend and he is addicted, hasn't taken it off",
            "the leather softened in a week and looks amazing, total head-turner on stage",
        ),
    ),
    _Archetype(
        pid="P-DOGCALMVEST", name="Calming Pressure Vest for Anxious Dogs", category="pet",
        base_units=78, early_growth=0.025, late_growth=0.20,
        start_sellers=4, seller_growth=0.02, start_promo=4, promo_growth=0.035,
        start_ads=2, ad_growth=0.045, avg_ad_age_today=6, price=36.99,
        reviews=(
            "my rescue finally slept through a thunderstorm, I actually cried, obsessed",
            "cannot believe the difference, vet suggested a pressure wrap and this works",
            "fireworks night was calm for the first time ever, this is amazing",
            "everyone in my dog group asked what I used, I love this thing",
            "cheaper than the anxiety meds and no groggy side effects, life-changing",
        ),
    ),
    _Archetype(
        pid="P-SOURDOUGHLAME", name="Sourdough Scoring Lame + Blades", category="hobby",
        base_units=52, early_growth=0.025, late_growth=0.17,
        start_sellers=3, seller_growth=0.02, start_promo=3, promo_growth=0.03,
        start_ads=2, ad_growth=0.04, avg_ad_age_today=7, price=21.99,
        reviews=(
            "my scoring finally looks like the bakery loaves, the ear is insane, obsessed!",
            "cannot believe the difference the curved blade made, I love it, wish I found it sooner",
            "everyone in my sourdough group asked about it, perfect gift, amazing quality",
            "comes with spare blades and a leather cover, feels so premium, addicted to scoring now",
        ),
    ),
    # ── COMMODITY TRAPS — the point of the exercise: these get REJECTED ──────────
    _Archetype(
        # The headline example: real pimple-patch competition is enormous. Given a
        # realistic seller/promo/ad load, the commodity-saturation gate disqualifies it
        # regardless of momentum — exactly what should happen.
        pid="P-PIMPLEPATCH", name="Hydrocolloid Pimple Patches", category="beauty",
        base_units=180, early_growth=0.02, late_growth=0.06,
        start_sellers=70, seller_growth=0.015, start_promo=150, promo_growth=0.02,
        start_ads=48, ad_growth=0.015, avg_ad_age_today=35, price=16.99,
        reviews=(
            "they work but literally every shop on tiktok sells the exact same patches",
            "saw identical ones on like 20 different stores, prices all over the place",
            "fine product, nothing special, it's a race to the bottom now",
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
    _Archetype(
        pid="P-POSTURECORR", name="Posture Corrector Belt", category="wellness",
        base_units=300, early_growth=0.00, late_growth=-0.02,
        start_sellers=45, seller_growth=0.05, start_promo=130, promo_growth=0.06,
        start_ads=65, ad_growth=0.05, avg_ad_age_today=55, price=21.99,
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
        reviews=("it's a phone stand. it holds my phone. everybody sells them.",),
    ),
    _Archetype(
        pid="P-CHEAPCABLE", name="Bargain USB Cable 3-pack", category="electronics",
        base_units=60, early_growth=0.02, late_growth=0.12,
        start_sellers=5, seller_growth=0.02, start_promo=3, promo_growth=0.03,
        start_ads=2, ad_growth=0.04, avg_ad_age_today=7, price=6.49,
        reviews=("works fine", "cheap and cheerful", "one stopped working after a month"),
    ),
    # ── COMPLIANCE DEMOS — gated on brand / restricted category ──────────────────
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
