"""Supplier catalog import — bring YOUR supplier's product list into the engine.

`feeds/csv_import.py` imports DEMAND data (Kalodata/FastMoss: units, GMV, price —
what the market is buying). This imports SUPPLY data (CJ/Zendrop/AutoDS: cost,
shipping cost, ship days, MOQ, warehouse — what you can actually get and for how
much). They are different halves and the engine needs both.

Why this matters more than it looks: a catalog row carries a REAL landed cost. That
is the one input the engine refuses to guess, and the thing currently gating economics
on every hand-added product. Importing your catalog fills that in for hundreds of
products at once, so `scorecard` can compute margin, break-even ROAS, and max CAC
instead of showing a locked gate.

THE HONEST LIMIT, and it is the whole reason `rank()` is separate from scoring:
a supplier catalog cannot tell you whether anything SELLS. It knows cost, shipping,
and specs. It knows nothing about demand. So catalog ranking produces a SHORTLIST
FOR RESEARCH — "these are worth 20 minutes of demand checking" — and never a TEST
verdict. The demand gates stay exactly where they are. A cheap product with a fat
theoretical margin and no demand is the single most common way a new store dies,
and a catalog ranked on margin alone points straight at it.

No scraping. You export the CSV from your supplier's own dashboard (all three majors
offer it) and import it here — the same rule as the Kalodata/FastMoss path.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Optional

from ..db import Database, models
from ..detection._stats import clamp
from .supplier import TARGET_SHIP_DAYS

# Column spellings across the three major supplier platforms plus generic exports.
# Extend with --map "Their Column=field" rather than editing this.
_SYNONYMS: dict[str, list[str]] = {
    "sku":          ["sku", "product id", "product_id", "id", "item id", "item_id",
                     "variant id", "pid", "cj product id"],
    "name":         ["name", "product", "product name", "product_name", "title",
                     "product title", "item name", "描述"],
    "category":     ["category", "product category", "category name", "type", "niche",
                     "main category", "分类"],
    "cost":         ["cost", "unit cost", "price", "product price", "wholesale price",
                     "supplier price", "base cost", "item cost", "cost price",
                     "your price", "成本"],
    "ship_cost":    ["ship cost", "ship_cost", "shipping", "shipping cost",
                     "shipping price", "shipping fee", "delivery cost", "freight",
                     "运费"],
    "ship_days":    ["ship days", "ship_days", "shipping time", "delivery time",
                     "lead time", "processing time", "delivery days", "eta",
                     "shipping days", "时效"],
    "moq":          ["moq", "min order", "minimum order", "min qty", "minimum quantity",
                     "min order quantity"],
    "warehouse":    ["warehouse", "ships from", "ship from", "origin", "location",
                     "country", "warehouse location", "stock location", "发货地"],
    "rating":       ["rating", "score", "supplier rating", "product rating", "stars"],
    "stock":        ["stock", "inventory", "qty", "quantity", "available", "in stock"],
    "url":          ["url", "link", "product url", "product link", "source url"],
}

_FIELDS = list(_SYNONYMS.keys())

# Recognised supplier platforms. The value is only a default display name — every
# preset reads through the same synonym table, because all three export similar shapes.
PRESETS = {
    "cj": "CJ Dropshipping",
    "zendrop": "Zendrop",
    "autods": "AutoDS",
    "spocket": "Spocket",
    "generic": "Supplier",
}

_US_HINTS = ("us", "usa", "united states", "u.s.", "america", "california", "ca",
             "new jersey", "nj", "texas", "tx", "illinois", "il")


@dataclass
class CatalogImport:
    source: str
    filename: str
    supplier_name: str
    products: int = 0
    suppliers: int = 0
    rows_skipped: int = 0
    skipped_reasons: list[str] = field(default_factory=list)
    column_map: dict[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        lines = [f"{self.products} product(s) + {self.suppliers} supplier quote(s) "
                 f"imported from {self.filename} ({self.supplier_name})"]
        if self.column_map:
            lines.append("  columns used: " + ", ".join(
                f"{f}←{h}" for f, h in sorted(self.column_map.items())))
        for f in _FIELDS:
            if f in ("cost", "name") and f not in self.column_map:
                lines.append(f"  ⚠ no '{f}' column matched — remap it with "
                             f'--map "Your Header={f}"')
        if self.rows_skipped:
            lines.append(f"  {self.rows_skipped} row(s) skipped:")
            lines += [f"    - {r}" for r in self.skipped_reasons[:8]]
            if len(self.skipped_reasons) > 8:
                lines.append(f"    … and {len(self.skipped_reasons) - 8} more")
        lines.append("")
        lines.append("These are CANDIDATES with real costs — not winners. A catalog "
                     "knows cost and shipping; it knows nothing about demand. Run "
                     "`catalog rank` for the research shortlist, then get real demand "
                     "data on the few you pick before any of them can reach TEST.")
        return "\n".join(lines)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _build_column_map(headers: list[str], overrides: dict[str, str]) -> dict[str, str]:
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


def _num(raw: Optional[str]) -> Optional[float]:
    """Parse '$4.20', '4,20', '3-7 days' (→3), '2 - 5' (→2). Ranges take the LOW end
    for costs and the HIGH end for times is tempting, but suppliers quote optimistic
    ranges either way — so take the low end consistently and let the sample order be
    the correction, rather than baking in a guess about their optimism."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("$", "").replace("%", "")
    if not s or s.lower() in {"-", "—", "n/a", "na", "null", "free"}:
        return 0.0 if s.lower() == "free" else None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def _is_us(raw: Optional[str]) -> bool:
    if not raw:
        return False
    v = _norm(raw)
    return any(re.search(rf"\b{re.escape(h)}\b", v) for h in _US_HINTS)


def slug_id(name: str, sku: str = "") -> str:
    base = sku.strip() or name.strip()
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:48]
    return slug or "item"


def import_catalog(
    db: Database,
    path: str | Path,
    supplier_name: str = "",
    source: str = "generic",
    overrides: Optional[dict[str, str]] = None,
    default_ship_days: float = 7.0,
) -> CatalogImport:
    """Import a supplier catalog CSV → Products + Supplier quotes, in one pass.

    A row needs a name (or SKU) and a cost. Everything else is optional and degrades
    honestly: no ship_days → `default_ship_days` with the assumption stated, no
    warehouse column → not treated as US. Unparseable rows are reported, never
    silently dropped."""
    path = Path(path)
    supplier_name = supplier_name or PRESETS.get(source, "Supplier")
    result = CatalogImport(source=source, filename=path.name, supplier_name=supplier_name)

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        result.column_map = _build_column_map(headers, overrides or {})
        cmap = result.column_map

        def get(row, field_name):
            header = cmap.get(field_name)
            return row.get(header) if header else None

        seen: set[str] = set()
        today = _date.today().isoformat()

        for i, row in enumerate(reader, start=2):
            name = (get(row, "name") or "").strip()
            sku = (get(row, "sku") or "").strip()
            if not name and not sku:
                result.rows_skipped += 1
                result.skipped_reasons.append(f"row {i}: no product name or SKU")
                continue
            cost = _num(get(row, "cost"))
            if cost is None:
                result.rows_skipped += 1
                result.skipped_reasons.append(
                    f"row {i}: '{name[:32] or sku}' has no parseable cost — the engine "
                    "will not invent one")
                continue

            pid = slug_id(name, sku)
            if pid in seen:
                continue
            seen.add(pid)

            category = (get(row, "category") or "uncategorized").strip().lower()
            db.upsert_product(models.Product(
                id=pid, name=name or sku, category=category,
                supplier_ref=f"{source}:{sku}" if sku else source,
                first_seen=today,
            ))
            result.products += 1

            ship_days = _num(get(row, "ship_days"))
            db.upsert_supplier(models.Supplier(
                ref=f"{source}:{sku or pid}",
                product_id=pid,
                name=supplier_name,
                cost=cost,
                ship_cost=_num(get(row, "ship_cost")) or 0.0,
                ship_days=ship_days if ship_days is not None else default_ship_days,
                moq=int(_num(get(row, "moq")) or 1),
                us_warehouse=_is_us(get(row, "warehouse")),
                rating=_num(get(row, "rating")) or 0.0,
                response_hrs=24.0,
                quality_notes=(get(row, "url") or "").strip(),
            ))
            result.suppliers += 1

    return result


# ── ranking: a research shortlist, explicitly NOT a verdict ───────────────────

@dataclass
class CatalogPick:
    product: models.Product
    supplier: models.Supplier
    landed: float
    target_price: float
    margin_pct: float
    supply_score: float          # 0..100 — SUPPLY quality only, never demand
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def line(self) -> str:
        # margin_pct is deliberately NOT shown: target_price is a fixed multiple of
        # landed cost, so the percentage is identical for every row and would read as
        # a differentiator while carrying no information. Ship origin does vary.
        origin = "US" if self.supplier.us_warehouse else "  "
        return (f"{self.supply_score:5.1f}  {self.product.name[:40]:40s} "
                f"${self.landed:6.2f} → ${self.target_price:7.2f}  "
                f"{self.supplier.ship_days:2.0f}d {origin}"
                + ("  ⚠ " + "; ".join(self.blockers) if self.blockers else ""))


# Price multiple a catalog item needs to support paid traffic. Below ~3x landed there
# is no room for the fee stack plus a CAC, which is why cheap-and-thin loses money.
MIN_MULTIPLE = 3.0
TARGET_MULTIPLE = 3.5

# The price band TikTok impulse buying actually lives in. Conversion falls off sharply
# above the ceiling — a product needing $120 to clear its cost is not an impulse buy,
# it is a considered purchase competing with Amazon, which is a different business.
IMPULSE_CEILING = 35.0
IMPULSE_SWEET = 25.0


def score_supply(product: models.Product, s: models.Supplier) -> CatalogPick:
    """Rank on what a catalog actually knows: landed cost, margin headroom inside the
    impulse price band, shipping speed, warehouse, and MOQ friction. No demand term
    appears here, because no demand information exists in a catalog."""
    landed = s.cost + s.ship_cost
    target_price = round(landed * TARGET_MULTIPLE, 2)
    margin_pct = (100 * (target_price - landed) / target_price) if target_price else 0.0

    reasons: list[str] = []
    blockers: list[str] = []

    # Margin headroom (45%) — measured as room between landed cost and the price
    # ceiling people will actually impulse-buy at. Scoring margin as a multiple of
    # cost would be a tautology: every item priced at 3.5x shows the same 71%.
    # What differs between items is how much of the impulse band the cost eats.
    margin_term = clamp((IMPULSE_CEILING - landed) / IMPULSE_CEILING, 0, 1)
    if target_price > IMPULSE_CEILING:
        blockers.append(f"needs ${target_price:.0f} to clear cost — above the "
                        f"~${IMPULSE_CEILING:.0f} impulse ceiling")
    elif target_price <= IMPULSE_SWEET:
        reasons.append(f"${target_price:.2f} sits in the impulse sweet spot")

    # Shipping speed (30%) — fulfillment breaks more new shops than bad products do.
    ship_term = clamp((14 - s.ship_days) / (14 - TARGET_SHIP_DAYS), 0, 1)
    if s.ship_days > 10:
        blockers.append(f"{s.ship_days:.0f}-day shipping is a refund machine")
    elif s.ship_days <= TARGET_SHIP_DAYS:
        reasons.append(f"{s.ship_days:.0f}-day shipping clears the target")

    # US warehouse (15%) — the single biggest lever on ship time and refunds.
    us_term = 1.0 if s.us_warehouse else 0.0
    if s.us_warehouse:
        reasons.append("US warehouse")

    # MOQ friction (10%) — a high MOQ turns a $150 test into an inventory bet.
    moq_term = 1.0 if s.moq <= 1 else clamp((50 - s.moq) / 49, 0, 1)
    if s.moq > 10:
        blockers.append(f"MOQ {s.moq} — that is inventory risk, not a test")

    total = 100 * (0.45 * margin_term + 0.30 * ship_term
                   + 0.15 * us_term + 0.10 * moq_term)

    if margin_term >= 0.8:
        reasons.append(f"${landed:.2f} landed leaves most of the impulse band as margin")
    if not reasons:
        reasons.append("no standout supply advantage")

    return CatalogPick(product=product, supplier=s, landed=landed,
                       target_price=target_price, margin_pct=margin_pct,
                       supply_score=round(total, 1), reasons=reasons, blockers=blockers)


# TikTok Shop's PERMANENTLY prohibited categories — never sellable at any price, so a
# fat supply margin on one is not a "candidate", it is a trap. This is a hard exclusion,
# separate from and stronger than the impulse/MOQ blockers (which are just economics).
# Matched against the product's `restricted` flag OR keywords in its category/name.
PROHIBITED_KEYWORDS = (
    "vape", "vaping", "e-cig", "ecig", "e-liquid", "nicotine", "tobacco", "cigarette",
    "cigar", "hookah", "alcohol", "liquor", "wine", "beer", "spirits", "cbd", "thc",
    "cannabis", "marijuana", "kratom", "weapon", "firearm", "ammo", "ammunition",
    "gun", "knife-set", "pepper-spray", "prescription", "adult-toy",
)


def is_prohibited(product: models.Product) -> tuple[bool, str]:
    """(prohibited?, why). Prohibited = the DB restricted flag, or a category/name that
    matches a permanently-banned category. This is a compliance verdict, not economics."""
    if getattr(product, "restricted", False):
        return True, "flagged as a restricted TikTok category"
    hay = f"{product.category} {product.name}".lower()
    for kw in PROHIBITED_KEYWORDS:
        if kw in hay:
            return True, f"'{kw}' is on TikTok Shop's permanently-prohibited list"
    return False, ""


def prohibited_products(db: Database) -> list[tuple[models.Product, str]]:
    """Products the catalog EXCLUDES from ranking because they cannot be listed at all.
    Surfaced separately so the exclusion is transparent, never a silent drop."""
    out = []
    for p in db.all_products():
        if not db.suppliers_for(p.id):
            continue
        banned, why = is_prohibited(p)
        if banned:
            out.append((p, why))
    return out


def rank(db: Database, top: int = 20, category: str = "",
         max_landed: float = 0.0) -> list[CatalogPick]:
    """The research shortlist, best supply economics first. Products with no supplier
    quote are excluded (nothing to rank them on); prohibited-category products are
    HARD-excluded (they cannot be listed — a supply score would be misleading)."""
    picks: list[CatalogPick] = []
    for p in db.all_products():
        if category and p.category != category.lower():
            continue
        if is_prohibited(p)[0]:            # never rank something that can't be sold
            continue
        suppliers = db.suppliers_for(p.id)
        if not suppliers:
            continue
        best = min(suppliers, key=lambda s: s.cost + s.ship_cost)
        if max_landed and (best.cost + best.ship_cost) > max_landed:
            continue
        picks.append(score_supply(p, best))
    picks.sort(key=lambda c: c.supply_score, reverse=True)
    return picks[:top]


def render_rank(picks: list[CatalogPick], has_demand=None) -> str:
    """`has_demand` is a callable(product_id) -> bool, so the renderer can say which
    picks still need demand research rather than implying they are ready to test."""
    if not picks:
        return ("No catalog products with supplier quotes yet.\n"
                "Import your supplier's CSV export: "
                "`catalog import <file.csv> --source cj|zendrop|autods|generic`\n")

    lines = ["# Catalog shortlist — ranked on SUPPLY economics only", ""]
    lines.append("Score is margin headroom, shipping speed, US warehouse, and MOQ. "
                 "There is no demand term, because a catalog contains no demand "
                 "information. This is a list of things worth researching, not a list "
                 "of things worth testing.")
    lines.append("")
    lines.append("score  product                                  landed →   price   ship")
    lines.append("─" * 78)
    for c in picks:
        lines.append(c.line)

    needs = [c for c in picks if has_demand and not has_demand(c.product.id)]
    lines.append("")
    if needs:
        lines.append(f"{len(needs)} of {len(picks)} have NO demand data yet. Until they "
                     "do, none can reach a TEST verdict — that gate is deliberate.")
        lines.append("  Next: pick 3, research real demand on each, then "
                     "`import-csv` or `add-metric` what you find.")
    lines.append("")
    lines.append("Then: `daily` to score, `scorecard <id>` to read the verdict, and "
                 "order a sample before any ad money moves.")
    return "\n".join(lines)
