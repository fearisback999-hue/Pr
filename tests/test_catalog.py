"""Supplier catalog import + supply ranking.

The property that matters most: a catalog is SUPPLY data. It must never be able to
push a product toward a TEST verdict on its own, because it contains no information
about whether anything sells.
"""

import pytest

from tt_engine.db import Database, models
from tt_engine.sourcing import catalog as cat


_CSV = """Product ID,Product Name,Category,Product Price,Shipping Cost,Delivery Time,Min Order,Ships From,Rating
CJ1,Scalp Massager Brush,beauty,1.15,0.95,4-6 days,1,US Warehouse - TX,4.7
CJ2,Oversized Lounge Set,apparel,11.50,3.20,12-18 days,1,China,4.1
CJ3,Heated Eye Massager,wellness,28.00,6.50,14-21 days,20,China,4.0
CJ4,No Cost Row,misc,,1.00,5 days,1,US,4.0
"""


def _write(tmp_path, text=_CSV, name="cat.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ── import ────────────────────────────────────────────────────────────────────

def test_import_creates_products_and_real_landed_costs(tmp_path):
    """The point of catalog import: it fills in the one number the engine refuses
    to guess, for a whole catalog at once."""
    with Database(str(tmp_path / "d.db")) as db:
        res = cat.import_catalog(db, _write(tmp_path), source="cj")
        assert res.products == 3 and res.suppliers == 3
        pid = cat.slug_id("Scalp Massager Brush", "CJ1")
        suppliers = db.suppliers_for(pid)
        assert suppliers
        s = suppliers[0]
        assert s.cost == 1.15 and s.ship_cost == 0.95
        assert s.us_warehouse is True
        assert s.ship_days == 4          # "4-6 days" → the low end
        assert s.name == "CJ Dropshipping"


def test_rows_without_a_cost_are_reported_never_invented(tmp_path):
    with Database(str(tmp_path / "d.db")) as db:
        res = cat.import_catalog(db, _write(tmp_path), source="cj")
    assert res.rows_skipped == 1
    assert "No Cost Row" in res.skipped_reasons[0]
    assert "will not invent one" in res.skipped_reasons[0]


def test_import_summary_says_candidates_not_winners(tmp_path):
    with Database(str(tmp_path / "d.db")) as db:
        summary = cat.import_catalog(db, _write(tmp_path), source="cj").summary
    assert "CANDIDATES" in summary
    assert "knows nothing about demand" in summary


def test_column_remapping_and_unknown_field_rejected(tmp_path):
    odd = "Widget,Wholesale,Ships From\nThing A,2.50,US\n"
    path = _write(tmp_path, odd, "odd.csv")
    with Database(str(tmp_path / "d.db")) as db:
        res = cat.import_catalog(db, path, overrides={"Widget": "name",
                                                      "Wholesale": "cost"})
        assert res.products == 1
        with pytest.raises(ValueError, match="unknown field"):
            cat.import_catalog(db, path, overrides={"Widget": "nonsense"})
        with pytest.raises(ValueError, match="not found in CSV headers"):
            cat.import_catalog(db, path, overrides={"Missing Col": "cost"})


def test_us_detection_does_not_false_positive_on_substrings(tmp_path):
    """'Australia' contains 'us'. Word-boundary matching, not substring."""
    assert cat._is_us("US Warehouse - CA")
    assert cat._is_us("United States, NJ")
    assert not cat._is_us("Australia")
    assert not cat._is_us("China")
    assert not cat._is_us("")


def test_free_shipping_parses_as_zero_not_missing():
    assert cat._num("free") == 0.0
    assert cat._num("$4.20") == 4.20
    assert cat._num("3-7 days") == 3.0
    assert cat._num("—") is None


# ── ranking ───────────────────────────────────────────────────────────────────

def test_ranking_differentiates_instead_of_tying(tmp_path):
    """Scoring margin as a multiple of cost is a tautology — every item priced at
    3.5x shows the same percentage and everything ties. Cost must actually matter."""
    with Database(str(tmp_path / "d.db")) as db:
        cat.import_catalog(db, _write(tmp_path), source="cj")
        picks = cat.rank(db)
    scores = [p.supply_score for p in picks]
    assert len(set(scores)) == len(scores), f"scores tied: {scores}"
    assert picks[0].product.name.startswith("Scalp"), "cheapest+fastest should lead"
    assert picks[-1].product.name.startswith("Heated"), "expensive+slow+MOQ should trail"


def test_products_above_the_impulse_ceiling_are_blocked(tmp_path):
    with Database(str(tmp_path / "d.db")) as db:
        cat.import_catalog(db, _write(tmp_path), source="cj")
        picks = {p.product.name: p for p in cat.rank(db)}
    heated = picks["Heated Eye Massager"]
    joined = "; ".join(heated.blockers)
    assert "impulse ceiling" in joined
    assert "refund machine" in joined      # 14-day shipping
    assert "MOQ 20" in joined


def test_ranking_carries_no_demand_signal(tmp_path):
    """Adding demand data must not change the SUPPLY score — they are separate axes,
    and conflating them is how a catalog starts looking like a verdict."""
    with Database(str(tmp_path / "d.db")) as db:
        cat.import_catalog(db, _write(tmp_path), source="cj")
        before = {p.product.id: p.supply_score for p in cat.rank(db)}
        pid = cat.slug_id("Scalp Massager Brush", "CJ1")
        db.upsert_metric(models.DailyMetric(
            product_id=pid, date="2026-01-01", units=500, gmv=9995.0, price=19.99,
            sellers=12, promo_videos=40, ads=6, avg_ad_age=9.0))
        after = {p.product.id: p.supply_score for p in cat.rank(db)}
    assert before == after


def test_render_flags_everything_lacking_demand_data(tmp_path):
    with Database(str(tmp_path / "d.db")) as db:
        cat.import_catalog(db, _write(tmp_path), source="cj")
        picks = cat.rank(db)
        text = cat.render_rank(picks, has_demand=lambda pid: bool(db.metrics_for(pid)))
    assert "3 of 3 have NO demand data" in text
    assert "none can reach a TEST verdict" in text
    assert "no demand term" in text


def test_render_is_helpful_when_empty(tmp_path):
    with Database(str(tmp_path / "d.db")) as db:
        text = cat.render_rank(cat.rank(db))
    assert "catalog import" in text


def test_filters_narrow_the_shortlist(tmp_path):
    with Database(str(tmp_path / "d.db")) as db:
        cat.import_catalog(db, _write(tmp_path), source="cj")
        assert len(cat.rank(db, category="apparel")) == 1
        assert all(p.landed <= 5.0 for p in cat.rank(db, max_landed=5.0))
        assert len(cat.rank(db, top=2)) == 2


def test_products_without_a_supplier_quote_are_excluded(tmp_path):
    """There is nothing to rank them on — showing them at zero would imply a judgment."""
    with Database(str(tmp_path / "d.db")) as db:
        db.upsert_product(models.Product(id="orphan", name="No Quote", category="home"))
        assert cat.rank(db) == []


# ── the web surface ───────────────────────────────────────────────────────────

def test_catalog_page_states_the_supply_only_limit(tmp_path):
    from tt_engine.web.server import page_catalog
    with Database(str(tmp_path / "d.db")) as db:
        cat.import_catalog(db, _write(tmp_path), source="cj")
        html = page_catalog(db)
    assert "no demand term" in html
    assert "needs research" in html
    assert "Scalp Massager Brush" in html


def test_catalog_page_guides_import_when_empty(tmp_path):
    from tt_engine.web.server import page_catalog
    with Database(str(tmp_path / "d.db")) as db:
        html = page_catalog(db)
    assert "catalog import" in html
    assert "will not invent a landed cost" in html


def test_catalog_is_in_the_nav():
    from tt_engine.web.render import _NAV
    assert ("Catalog", "/catalog") in _NAV
