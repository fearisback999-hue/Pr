"""Part 5 — Economics & Offer. Compute the math, never guess.

A thin-margin product cannot be saved by a good ad, because you cannot afford to buy
the customer. The offer (price, bundle, free-ship threshold, upsell) is part of product
selection, not separate from it.
"""

from .calculator import (
    FEE_RATE, MARGIN_FLOOR, MARGIN_TARGET, Economics, compute_economics, unknown_economics,
)
from .offer import Offer, apply_offer

__all__ = [
    "Economics", "compute_economics", "unknown_economics",
    "FEE_RATE", "MARGIN_FLOOR", "MARGIN_TARGET", "Offer", "apply_offer",
]
