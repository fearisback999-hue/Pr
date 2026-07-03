"""SQLite wrapper. Stdlib only. Stores and retrieves the Part 12 tables and exposes
just enough query helpers for the detection / scoring / reporting stages."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from . import models

_SCHEMA = Path(__file__).resolve().parent / "schema.sql"


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(_SCHEMA.read_text())
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Lightweight, idempotent column additions for DBs created by older schema."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(products)")}
        if "reviews" not in cols:
            self.conn.execute("ALTER TABLE products ADD COLUMN reviews TEXT NOT NULL DEFAULT '[]'")
        ccols = {r["name"] for r in self.conn.execute("PRAGMA table_info(creatives)")}
        if "meta" not in ccols:
            self.conn.execute("ALTER TABLE creatives ADD COLUMN meta TEXT NOT NULL DEFAULT '{}'")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── products ───────────────────────────────────────────────────────────────
    def upsert_product(self, p: models.Product) -> None:
        self.conn.execute(
            """INSERT INTO products
                 (id, name, category, supplier_ref, first_seen, branded, restricted, reviews)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, category=excluded.category,
                 supplier_ref=excluded.supplier_ref, branded=excluded.branded,
                 restricted=excluded.restricted, reviews=excluded.reviews""",
            (p.id, p.name, p.category, p.supplier_ref, p.first_seen,
             int(p.branded), int(p.restricted), json.dumps(p.reviews)),
        )
        self.conn.commit()

    def get_product(self, product_id: str) -> Optional[models.Product]:
        row = self.conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        return _to_product(row) if row else None

    def all_products(self) -> list[models.Product]:
        rows = self.conn.execute("SELECT * FROM products ORDER BY first_seen").fetchall()
        return [_to_product(r) for r in rows]

    # ── daily metrics ──────────────────────────────────────────────────────────
    def upsert_metric(self, m: models.DailyMetric) -> None:
        self.conn.execute(
            """INSERT INTO product_daily_metrics
                 (product_id, date, units, gmv, price, sellers, promo_videos, ads, avg_ad_age)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(product_id, date) DO UPDATE SET
                 units=excluded.units, gmv=excluded.gmv, price=excluded.price,
                 sellers=excluded.sellers, promo_videos=excluded.promo_videos,
                 ads=excluded.ads, avg_ad_age=excluded.avg_ad_age""",
            (m.product_id, m.date, m.units, m.gmv, m.price, m.sellers,
             m.promo_videos, m.ads, m.avg_ad_age),
        )
        self.conn.commit()

    def upsert_metrics(self, metrics: Iterable[models.DailyMetric]) -> None:
        for m in metrics:
            self.upsert_metric(m)

    def metrics_for(self, product_id: str) -> list[models.DailyMetric]:
        rows = self.conn.execute(
            "SELECT * FROM product_daily_metrics WHERE product_id=? ORDER BY date",
            (product_id,),
        ).fetchall()
        return [_to_metric(r) for r in rows]

    # ── scores ─────────────────────────────────────────────────────────────────
    def upsert_score(self, s: models.Score) -> None:
        self.conn.execute(
            """INSERT INTO scores
                 (product_id, date, viral_demo, market_demand, competition_timing,
                  economics, content_potential, brand_potential, total,
                  gates_passed, gate_failures, window_days)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(product_id, date) DO UPDATE SET
                 viral_demo=excluded.viral_demo, market_demand=excluded.market_demand,
                 competition_timing=excluded.competition_timing, economics=excluded.economics,
                 content_potential=excluded.content_potential, brand_potential=excluded.brand_potential,
                 total=excluded.total, gates_passed=excluded.gates_passed,
                 gate_failures=excluded.gate_failures, window_days=excluded.window_days""",
            (s.product_id, s.date, s.viral_demo, s.market_demand, s.competition_timing,
             s.economics, s.content_potential, s.brand_potential, s.total,
             int(s.gates_passed), json.dumps(s.gate_failures), s.window_days),
        )
        self.conn.commit()

    def latest_score(self, product_id: str) -> Optional[models.Score]:
        row = self.conn.execute(
            "SELECT * FROM scores WHERE product_id=? ORDER BY date DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        return _to_score(row) if row else None

    def board(self, threshold: float = 0.0, gated_only: bool = False) -> list[models.Score]:
        """Latest score per product, ranked by total descending (Appendix A board)."""
        rows = self.conn.execute(
            """SELECT s.* FROM scores s
               JOIN (SELECT product_id, MAX(date) md FROM scores GROUP BY product_id) latest
                 ON s.product_id = latest.product_id AND s.date = latest.md
               WHERE s.total >= ?
               ORDER BY s.total DESC""",
            (threshold,),
        ).fetchall()
        scores = [_to_score(r) for r in rows]
        if gated_only:
            scores = [s for s in scores if s.gates_passed]
        return scores

    # ── suppliers ──────────────────────────────────────────────────────────────
    def upsert_supplier(self, s: models.Supplier) -> None:
        self.conn.execute(
            """INSERT INTO suppliers
                 (ref, product_id, name, cost, ship_cost, ship_days, moq,
                  us_warehouse, rating, response_hrs, quality_notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(ref) DO UPDATE SET
                 product_id=excluded.product_id, name=excluded.name, cost=excluded.cost,
                 ship_cost=excluded.ship_cost, ship_days=excluded.ship_days, moq=excluded.moq,
                 us_warehouse=excluded.us_warehouse, rating=excluded.rating,
                 response_hrs=excluded.response_hrs, quality_notes=excluded.quality_notes""",
            (s.ref, s.product_id, s.name, s.cost, s.ship_cost, s.ship_days, s.moq,
             int(s.us_warehouse), s.rating, s.response_hrs, s.quality_notes),
        )
        self.conn.commit()

    def suppliers_for(self, product_id: str) -> list[models.Supplier]:
        rows = self.conn.execute(
            "SELECT * FROM suppliers WHERE product_id=?", (product_id,)
        ).fetchall()
        return [_to_supplier(r) for r in rows]

    # ── creatives ──────────────────────────────────────────────────────────────
    def upsert_creative(self, c: models.Creative) -> None:
        self.conn.execute(
            """INSERT INTO creatives(id, product_id, format, hook, hook_type, soul_id,
                                     asset_url, status, meta)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 format=excluded.format, hook=excluded.hook, hook_type=excluded.hook_type,
                 soul_id=excluded.soul_id, asset_url=excluded.asset_url, status=excluded.status,
                 meta=excluded.meta""",
            (c.id, c.product_id, c.format, c.hook, c.hook_type, c.soul_id, c.asset_url,
             c.status, json.dumps(c.meta)),
        )
        self.conn.commit()

    def creatives_for(self, product_id: str) -> list[models.Creative]:
        rows = self.conn.execute(
            "SELECT * FROM creatives WHERE product_id=?", (product_id,)
        ).fetchall()
        return [_to_creative(r) for r in rows]

    def all_creatives(self) -> list[models.Creative]:
        rows = self.conn.execute("SELECT * FROM creatives").fetchall()
        return [_to_creative(r) for r in rows]

    # ── import audit log ───────────────────────────────────────────────────────
    def log_import(self, source: str, filename: str, products: int,
                   metric_rows: int, rows_skipped: int) -> None:
        self.conn.execute(
            """INSERT INTO import_log(source, filename, products, metric_rows, rows_skipped)
               VALUES(?,?,?,?,?)""",
            (source, filename, products, metric_rows, rows_skipped),
        )
        self.conn.commit()

    def import_history(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM import_log ORDER BY imported_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── tests / results ────────────────────────────────────────────────────────
    def upsert_test(self, t: models.Test) -> None:
        self.conn.execute(
            """INSERT INTO tests
                 (id, creative_id, date, spend, impressions, three_sec_vr, ctr, atc, cvr, roas)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 spend=excluded.spend, impressions=excluded.impressions,
                 three_sec_vr=excluded.three_sec_vr, ctr=excluded.ctr,
                 atc=excluded.atc, cvr=excluded.cvr, roas=excluded.roas""",
            (t.id, t.creative_id, t.date, t.spend, t.impressions, t.three_sec_vr,
             t.ctr, t.atc, t.cvr, t.roas),
        )
        self.conn.commit()

    def tests_for_product(self, product_id: str) -> list[models.Test]:
        rows = self.conn.execute(
            """SELECT t.* FROM tests t
               JOIN creatives c ON t.creative_id = c.id
               WHERE c.product_id = ? ORDER BY t.date""",
            (product_id,),
        ).fetchall()
        return [_to_test(r) for r in rows]

    def latest_result(self, product_id: str) -> Optional[models.Result]:
        row = self.conn.execute(
            "SELECT * FROM results WHERE product_id=? ORDER BY date DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        return _to_result(row) if row else None

    def upsert_result(self, r: models.Result) -> None:
        self.conn.execute(
            """INSERT INTO results(product_id, date, net_margin, refund_rate, roas, decision)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(product_id, date) DO UPDATE SET
                 net_margin=excluded.net_margin, refund_rate=excluded.refund_rate,
                 roas=excluded.roas, decision=excluded.decision""",
            (r.product_id, r.date, r.net_margin, r.refund_rate, r.roas, r.decision),
        )
        self.conn.commit()

    def all_results(self) -> list[models.Result]:
        rows = self.conn.execute("SELECT * FROM results ORDER BY date").fetchall()
        return [_to_result(r) for r in rows]


# ── row → dataclass converters ─────────────────────────────────────────────────
def _to_product(r: sqlite3.Row) -> models.Product:
    return models.Product(
        id=r["id"], name=r["name"], category=r["category"], supplier_ref=r["supplier_ref"],
        first_seen=r["first_seen"], branded=bool(r["branded"]), restricted=bool(r["restricted"]),
        reviews=json.loads(r["reviews"]) if r["reviews"] else [],
    )


def _to_metric(r: sqlite3.Row) -> models.DailyMetric:
    return models.DailyMetric(
        product_id=r["product_id"], date=r["date"], units=r["units"], gmv=r["gmv"],
        price=r["price"], sellers=r["sellers"], promo_videos=r["promo_videos"],
        ads=r["ads"], avg_ad_age=r["avg_ad_age"],
    )


def _to_score(r: sqlite3.Row) -> models.Score:
    return models.Score(
        product_id=r["product_id"], date=r["date"], viral_demo=r["viral_demo"],
        market_demand=r["market_demand"], competition_timing=r["competition_timing"],
        economics=r["economics"], content_potential=r["content_potential"],
        brand_potential=r["brand_potential"], total=r["total"],
        gates_passed=bool(r["gates_passed"]),
        gate_failures=json.loads(r["gate_failures"]) if r["gate_failures"] else [],
        window_days=r["window_days"],
    )


def _to_supplier(r: sqlite3.Row) -> models.Supplier:
    return models.Supplier(
        ref=r["ref"], product_id=r["product_id"], name=r["name"], cost=r["cost"],
        ship_cost=r["ship_cost"], ship_days=r["ship_days"], moq=r["moq"],
        us_warehouse=bool(r["us_warehouse"]), rating=r["rating"],
        response_hrs=r["response_hrs"], quality_notes=r["quality_notes"],
    )


def _to_creative(r: sqlite3.Row) -> models.Creative:
    keys = r.keys()
    meta = json.loads(r["meta"]) if "meta" in keys and r["meta"] else {}
    return models.Creative(
        id=r["id"], product_id=r["product_id"], format=r["format"], hook=r["hook"],
        hook_type=r["hook_type"], soul_id=r["soul_id"], asset_url=r["asset_url"],
        status=r["status"], meta=meta,
    )


def _to_test(r: sqlite3.Row) -> models.Test:
    return models.Test(
        id=r["id"], creative_id=r["creative_id"], date=r["date"], spend=r["spend"],
        impressions=r["impressions"], three_sec_vr=r["three_sec_vr"], ctr=r["ctr"],
        atc=r["atc"], cvr=r["cvr"], roas=r["roas"],
    )


def _to_result(r: sqlite3.Row) -> models.Result:
    return models.Result(
        product_id=r["product_id"], date=r["date"], net_margin=r["net_margin"],
        refund_rate=r["refund_rate"], roas=r["roas"], decision=r["decision"],
    )
