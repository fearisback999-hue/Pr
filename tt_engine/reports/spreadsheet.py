"""Appendix A — the scoring spreadsheet. One row per product with the exact columns the
brief specifies, sorted by total descending. Filter gates = Y and total ≥ threshold to
get the shortlist. Exports to CSV so you can pivot it in a sheet."""

from __future__ import annotations

import csv
from pathlib import Path

from ..config import CONFIG
from ..db import Database

# Appendix A column order.
COLUMNS = [
    "name", "category", "supplier_cost", "ship_days", "sell_price", "gross_margin_pct",
    "breakeven_roas", "units_per_day", "wow_growth_pct", "seller_count", "promo_video_count",
    "window_days", "viral_demo", "market_demand", "competition_timing", "economics",
    "content_potential", "brand_potential", "total", "gates_passed", "verdict", "date_scored",
]


def board_rows(db: Database, threshold: float | None = None) -> list[dict]:
    """Assemble Appendix A rows for every product that has a daily metric series."""
    from ..pipeline import score_stored  # lazy import avoids a reports↔pipeline cycle

    bar = CONFIG.score_threshold if threshold is None else threshold
    rows: list[dict] = []
    for product in db.all_products():
        sr = score_stored(db, product.id)
        if sr is None:  # synthetic/score-only products with no metric series
            continue
        metrics = db.metrics_for(product.id)
        latest = metrics[-1]
        suppliers = db.suppliers_for(product.id)
        best = min(suppliers, key=lambda s: s.cost + s.ship_cost) if suppliers else None
        s = sr.breakdown.score
        m = sr.trigger.momentum
        verdict = ("ATTACK" if (s.gates_passed and s.total >= bar)
                   else ("watch" if s.gates_passed else "GATED"))
        rows.append({
            "name": product.name,
            "category": product.category,
            "supplier_cost": round(best.cost + best.ship_cost, 2) if best else "",
            "ship_days": best.ship_days if best else "",
            "sell_price": latest.price,
            "gross_margin_pct": round(sr.economics.gross_margin * 100, 1),
            "breakeven_roas": ("inf" if sr.economics.breakeven_roas == float("inf")
                               else round(sr.economics.breakeven_roas, 2)),
            "units_per_day": round(m.velocity_7d, 0),
            "wow_growth_pct": round(m.wow_growth * 100, 0),
            "seller_count": latest.sellers,
            "promo_video_count": latest.promo_videos,
            "window_days": s.window_days,
            "viral_demo": s.viral_demo,
            "market_demand": s.market_demand,
            "competition_timing": s.competition_timing,
            "economics": s.economics,
            "content_potential": s.content_potential,
            "brand_potential": s.brand_potential,
            "total": s.total,
            "gates_passed": "Y" if s.gates_passed else "N",
            "verdict": verdict,
            "date_scored": s.date,
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def export_csv(db: Database, path: str, threshold: float | None = None) -> int:
    """Write the Appendix A board to CSV. Returns the number of rows written."""
    rows = board_rows(db, threshold)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
