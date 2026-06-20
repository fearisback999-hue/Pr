"""Kalodata (Enterprise) adapter — primary velocity / saturation source (Part 2).

Kalodata Enterprise exposes an API for sales velocity, saturation, and winning videos.
Implement fetch() to map its response onto FeedRecord/DailyMetric. This stub raises a
clear error until wired, so the engine fails loud rather than silently using stale data.
"""

from __future__ import annotations

from typing import Optional

from ..config import CONFIG
from .base import DataFeed, FeedRecord


class KalodataFeed(DataFeed):
    name = "kalodata"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or CONFIG.kalodata_api_key

    def fetch(self, lookback_days: int = 35, limit: Optional[int] = None) -> list[FeedRecord]:
        if not self.api_key:
            raise RuntimeError(
                "KALODATA_API_KEY is not set. Set it in .env, or use TT_PRIMARY_FEED=mock."
            )
        # ── Integration point ──────────────────────────────────────────────────
        # import requests
        # resp = requests.get(
        #     "https://api.kalodata.com/v1/products/trending",
        #     headers={"Authorization": f"Bearer {self.api_key}"},
        #     params={"window": lookback_days, "limit": limit or 100, "region": "US"},
        #     timeout=30,
        # )
        # resp.raise_for_status()
        # Map each product's daily series onto models.DailyMetric(units, gmv, price,
        # sellers, promo_videos, ads, avg_ad_age) and wrap in FeedRecord. Pull the
        # review/comment corpus too if available, for the Part 4 psychology pass.
        raise NotImplementedError(
            "KalodataFeed.fetch() — map the Kalodata API response onto FeedRecord. "
            "See the commented template in this file."
        )
