"""The data-feed contract every adapter implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..db import models


@dataclass
class FeedRecord:
    """One product plus its daily metric time series, as returned by a feed."""
    product: models.Product
    metrics: list[models.DailyMetric] = field(default_factory=list)
    # Optional reviews/comments corpus for the Part 4 psychology pass.
    reviews: list[str] = field(default_factory=list)


class DataFeed:
    """Base class. A real adapter implements fetch() against its vendor API.

    The detection logic only needs the daily time series in `product_daily_metrics`
    shape: units, gmv, price, sellers, promo_videos, ads, avg_ad_age. Map the vendor's
    fields onto that and the rest of the engine works unchanged.
    """

    name: str = "base"

    def fetch(self, lookback_days: int = 35, limit: Optional[int] = None) -> list[FeedRecord]:
        raise NotImplementedError(
            f"{type(self).__name__}.fetch() not implemented — wire it to the vendor API"
        )
