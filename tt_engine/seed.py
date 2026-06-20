"""Seed the database for an offline demo run.

  • seed_sample()        — mock feed (products + 35-day metrics) + suppliers tuned so each
                           archetype lands on its intended outcome (one clean ATTACK,
                           the rest each tripping a different gate).
  • seed_demo_outcomes() — synthetic scored products + labeled results so the Part 13
                           recalibration has a real sample to fit (≥20 winners/losers).
"""

from __future__ import annotations

import random
from datetime import date as _date

from .db import Database, models
from .feeds import MockFeed

# Supplier rows tuned to control the demo's gate outcomes (see docstring).
_SUPPLIERS = [
    # ref, product_id, name, cost, ship_cost, ship_days, moq, us_wh, rating, resp_hrs, notes
    ("SUP-P-SCALPMASSAGER", "P-SCALPMASSAGER", "Shenzhen Relax Co", 6.0, 1.5, 4, 50, True, 4.7, 6,
     "sample passed, custom/private label available"),
    ("SUP-P-LEDHOODIE", "P-LEDHOODIE", "Glow Apparel Ltd", 12.0, 2.0, 6, 100, False, 4.3, 14,
     "good quality, sizing runs small"),
    ("SUP-P-POSTURECORR", "P-POSTURECORR", "Wellness OEM", 5.0, 1.0, 8, 200, False, 4.1, 20,
     "commoditized, many sellers"),
    ("SUP-P-PHONESTAND", "P-PHONESTAND", "Generic Accessories", 5.0, 0.5, 6, 500, False, 3.9, 30,
     "cheap, low differentiation"),
    ("SUP-P-CHEAPCABLE", "P-CHEAPCABLE", "Cable Factory", 4.5, 0.3, 7, 300, False, 4.0, 18,
     "thin margins, some complaints about durability"),
    ("SUP-P-BRANDPLUSH", "P-BRANDPLUSH", "Licensed Toys Inc", 7.0, 1.5, 5, 100, True, 4.6, 10,
     "licensed product"),
    ("SUP-P-VAPEKIT", "P-VAPEKIT", "Vapor Supply", 3.0, 0.5, 5, 100, True, 4.2, 12, "restricted category"),
    ("SUP-P-PIMPLEPATCH", "P-PIMPLEPATCH", "ClearSkin OEM", 3.0, 1.0, 4, 100, True, 4.7, 8,
     "sample passed, consumable — repeat purchase, private label available"),
    ("SUP-P-MAGSPRAY", "P-MAGSPRAY", "Calm Labs", 4.5, 1.0, 4, 100, True, 4.6, 10,
     "sample passed, consumable — repeat purchase"),
    ("SUP-P-TRENDYTUMBLER", "P-TRENDYTUMBLER", "Drinkware Factory", 9.0, 2.0, 6, 200, False, 4.0, 20,
     "commoditized, everyone sells it"),
]


def seed_sample(db: Database, lookback: int = 35) -> int:
    feed = MockFeed()
    records = feed.fetch(lookback_days=lookback)
    for rec in records:
        rec.product.reviews = rec.reviews  # persist corpus for reproducible scoring
        db.upsert_product(rec.product)
        db.upsert_metrics(rec.metrics)
    for ref, pid, name, cost, ship_cost, ship_days, moq, us_wh, rating, resp, notes in _SUPPLIERS:
        db.upsert_supplier(models.Supplier(
            ref=ref, product_id=pid, name=name, cost=cost, ship_cost=ship_cost,
            ship_days=ship_days, moq=moq, us_warehouse=us_wh, rating=rating,
            response_hrs=resp, quality_notes=notes,
        ))
    return len(records)


def seed_demo_outcomes(db: Database, n: int = 30, seed: int = 11) -> int:
    """Synthetic history where economics + market_demand truly predict winners, so the
    recalibration visibly upweights them. Illustrative only."""
    rng = random.Random(seed)
    today = _date.today().isoformat()
    for i in range(n):
        # Random-ish sub-scores within their caps.
        viral = rng.uniform(8, 18)
        market = rng.uniform(6, 20)
        comp = rng.uniform(5, 14)
        econ = rng.uniform(6, 20)
        content = rng.uniform(6, 14)
        brand = rng.uniform(3, 10)
        total = viral + market + comp + econ + content + brand
        # Ground-truth winner driven mostly by economics + market_demand (+ noise).
        signal = (econ / 20) * 0.5 + (market / 20) * 0.4 + rng.uniform(-0.15, 0.15)
        win = signal > 0.5
        pid = f"D-{i:02d}"
        db.upsert_product(models.Product(id=pid, name=f"Demo Product {i}", category="home"))
        db.upsert_score(models.Score(
            product_id=pid, date=today, viral_demo=round(viral, 2), market_demand=round(market, 2),
            competition_timing=round(comp, 2), economics=round(econ, 2),
            content_potential=round(content, 2), brand_potential=round(brand, 2),
            total=round(total, 2), gates_passed=True, gate_failures=[], window_days=20,
        ))
        db.upsert_result(models.Result(
            product_id=pid, date=today,
            net_margin=round(rng.uniform(0.02, 0.25) if win else rng.uniform(-0.15, 0.03), 3),
            refund_rate=round(rng.uniform(0.01, 0.05), 3),
            roas=round(rng.uniform(1.6, 3.5) if win else rng.uniform(0.6, 1.5), 2),
            decision="scale" if win else "kill",
        ))
    return n
