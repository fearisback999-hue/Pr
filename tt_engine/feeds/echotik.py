"""EchoTik adapter — cheap backup velocity source with Growth Velocity alerts (Part 2).

Stack this with Kalodata and cross-confirm a trigger before trusting it (Part 2: "stack
two velocity sources"). EchoTik has an API plus a Chrome extension; this adapter targets
the API. Implement fetch() to map its response onto FeedRecord/DailyMetric.
"""

from __future__ import annotations

from typing import Optional

from ..config import CONFIG
from .base import DataFeed, FeedRecord


class EchoTikFeed(DataFeed):
    name = "echotik"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or CONFIG.echotik_api_key

    def fetch(self, lookback_days: int = 35, limit: Optional[int] = None) -> list[FeedRecord]:
        if not self.api_key:
            raise RuntimeError(
                "ECHOTIK_API_KEY is not set. Set it in .env, or use TT_PRIMARY_FEED=mock."
            )
        # ── Integration point ──────────────────────────────────────────────────
        # import requests
        # resp = requests.get(
        #     "https://api.echotik.live/v1/growth-velocity",
        #     headers={"x-api-key": self.api_key},
        #     params={"days": lookback_days, "limit": limit or 100},
        #     timeout=30,
        # )
        # resp.raise_for_status()
        # Map onto FeedRecord/DailyMetric exactly as in kalodata.py.
        raise NotImplementedError(
            "EchoTikFeed.fetch() — map the EchoTik API response onto FeedRecord."
        )
