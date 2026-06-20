"""Part 6 — Sourcing & Fulfillment. Fulfillment breaks more new shops than bad products
do: slow shipping → refunds → tanked Shop Performance Score → throttled reach. Score
suppliers, target sub-5-day delivery, and make a sample order mandatory before scaling."""

from .supplier import TARGET_SHIP_DAYS, SupplierScore, rank_suppliers, score_supplier

__all__ = ["SupplierScore", "score_supplier", "rank_suppliers", "TARGET_SHIP_DAYS"]
