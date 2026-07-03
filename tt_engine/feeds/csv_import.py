"""CSV importers for manually-exported Kalodata / FastMoss data (Phase 1).

No scrapers, no vendor API calls — you export the CSV by hand from the vendor UI and
import it here. Column headers vary across vendor export versions, so matching is
case-insensitive over a synonym list, and any column can be remapped explicitly with
`--map "Vendor Column=field"`.

Each row needs at minimum: a product name (or id), a date, and two of units/gmv/price
(the third is derived). Rows that can't be parsed are skipped and reported — never
silently dropped.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date as _date, datetime
from pathlib import Path
from typing import Optional

from ..db import Database, models

# Canonical fields the engine needs, mapped from common vendor header spellings.
# Kalodata and FastMoss rename columns across export versions; extend via --map.
_SYNONYMS: dict[str, list[str]] = {
    "product_id":   ["product_id", "product id", "id", "sku", "item_id", "item id"],
    "name":         ["name", "product", "product name", "product_name", "title",
                     "product title", "商品名称"],
    "category":     ["category", "product category", "category name", "niche"],
    "date":         ["date", "day", "stat date", "stat_date", "data date", "日期"],
    "units":        ["units", "units sold", "unit sales", "sales", "sales volume",
                     "sold", "orders", "items sold", "daily sales", "sales(d)", "销量"],
    "gmv":          ["gmv", "revenue", "sales amount", "sales revenue", "turnover",
                     "gmv(d)", "daily revenue", "销售额"],
    "price":        ["price", "avg price", "average price", "unit price", "sale price",
                     "selling price", "客单价"],
    "sellers":      ["sellers", "seller count", "shops", "shop count", "stores",
                     "creators selling", "related shops"],
    "promo_videos": ["promo_videos", "videos", "video count", "related videos",
                     "promo videos", "video number", "relevant videos"],
    "ads":          ["ads", "ad count", "running ads", "active ads", "ad number"],
    "avg_ad_age":   ["avg_ad_age", "avg ad age", "ad age", "average ad age",
                     "avg ad age (days)"],
}

_FIELDS = list(_SYNONYMS.keys())


@dataclass
class ImportSummary:
    source: str
    filename: str
    products: int = 0
    metric_rows: int = 0
    rows_skipped: int = 0
    skipped_reasons: list[str] = field(default_factory=list)
    column_map: dict[str, str] = field(default_factory=dict)  # field -> CSV header used

    @property
    def summary(self) -> str:
        lines = [
            f"[{self.source}] {self.filename}: {self.products} product(s), "
            f"{self.metric_rows} metric row(s), {self.rows_skipped} skipped"
        ]
        if self.column_map:
            mapped = ", ".join(f"{f}←'{h}'" for f, h in sorted(self.column_map.items()))
            lines.append(f"  columns: {mapped}")
        for r in self.skipped_reasons[:10]:
            lines.append(f"  skipped: {r}")
        if len(self.skipped_reasons) > 10:
            lines.append(f"  … and {len(self.skipped_reasons) - 10} more")
        return "\n".join(lines)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _build_column_map(headers: list[str], overrides: dict[str, str]) -> dict[str, str]:
    """field -> actual CSV header. Overrides ('Vendor Col=field') win over synonyms."""
    out: dict[str, str] = {}
    normed = {_norm(h): h for h in headers}
    for header, fieldname in overrides.items():
        if fieldname not in _FIELDS:
            raise ValueError(f"unknown field '{fieldname}' in --map (choose from {_FIELDS})")
        if _norm(header) not in normed:
            raise ValueError(f"--map column '{header}' not found in CSV headers {headers}")
        out[fieldname] = normed[_norm(header)]
    for fieldname, syns in _SYNONYMS.items():
        if fieldname in out:
            continue
        for syn in syns:
            if syn in normed:
                out[fieldname] = normed[syn]
                break
    return out


_NUM_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9, "w": 1e4}  # w = 万 in CN exports


def _num(raw: Optional[str]) -> Optional[float]:
    """Parse vendor-formatted numbers: '$1,234.50', '1.2k', '3.4M', '12%', '—'."""
    if raw is None:
        return None
    s = raw.strip().replace(",", "").replace("$", "").replace("%", "")
    if not s or s in {"-", "—", "n/a", "na", "null"}:
        return None
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*([kKmMbBwW]?)", s)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2).lower()
    return val * _NUM_SUFFIX.get(suffix, 1.0)


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%Y%m%d")


def _parse_date(raw: Optional[str], default: Optional[str] = None) -> Optional[str]:
    if raw is None or not raw.strip():
        return default
    s = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def slug_id(name: str) -> str:
    """Deterministic product id from a name: 'Scalp Massager Pro' → 'P-SCALPMASSAGERPRO'."""
    return "P-" + re.sub(r"[^A-Z0-9]", "", name.upper())[:24]


def import_csv(
    db: Database,
    path: str,
    source: str = "generic",
    column_map: Optional[dict[str, str]] = None,
    default_category: str = "home",
) -> ImportSummary:
    """Import one vendor CSV into products + product_daily_metrics. Idempotent —
    re-importing the same file upserts the same rows. Every import is logged."""
    p = Path(path)
    result = ImportSummary(source=source, filename=p.name)
    with p.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"{path}: empty CSV (no header row)")
        cols = _build_column_map(list(reader.fieldnames), column_map or {})
        result.column_map = dict(cols)

        if "name" not in cols and "product_id" not in cols:
            raise ValueError(
                f"{path}: no product name/id column found in {reader.fieldnames}. "
                f"Remap one with --map \"Your Column=name\"."
            )

        seen_products: set[str] = set()
        today = _date.today().isoformat()
        for i, row in enumerate(reader, start=2):  # header is line 1
            def get(fieldname: str) -> Optional[str]:
                h = cols.get(fieldname)
                return row.get(h) if h else None

            name = (get("name") or "").strip()
            pid = (get("product_id") or "").strip() or (slug_id(name) if name else "")
            if not pid:
                result.rows_skipped += 1
                result.skipped_reasons.append(f"line {i}: no product name/id")
                continue

            date = _parse_date(get("date"), default=today)
            if date is None:
                result.rows_skipped += 1
                result.skipped_reasons.append(f"line {i}: unparseable date '{get('date')}'")
                continue

            units = _num(get("units"))
            gmv = _num(get("gmv"))
            price = _num(get("price"))
            # Derive the missing one of units/gmv/price from the other two.
            if price is None and gmv is not None and units:
                price = gmv / units
            if gmv is None and price is not None and units is not None:
                gmv = price * units
            if units is None and gmv is not None and price:
                units = gmv / price
            if units is None or gmv is None or price is None:
                result.rows_skipped += 1
                result.skipped_reasons.append(
                    f"line {i} ({pid}): need two of units/gmv/price "
                    f"(got units={get('units')!r} gmv={get('gmv')!r} price={get('price')!r})"
                )
                continue

            if pid not in seen_products:
                existing = db.get_product(pid)
                if existing is None:
                    db.upsert_product(models.Product(
                        id=pid, name=name or pid,
                        category=(get("category") or default_category).strip().lower(),
                        first_seen=date,
                    ))
                result.products += 1
                seen_products.add(pid)

            db.upsert_metric(models.DailyMetric(
                product_id=pid, date=date,
                units=int(round(units)), gmv=round(gmv, 2), price=round(price, 2),
                sellers=int(_num(get("sellers")) or 0),
                promo_videos=int(_num(get("promo_videos")) or 0),
                ads=int(_num(get("ads")) or 0),
                avg_ad_age=float(_num(get("avg_ad_age")) or 0.0),
            ))
            result.metric_rows += 1

    db.log_import(source, p.name, result.products, result.metric_rows, result.rows_skipped)
    return result
