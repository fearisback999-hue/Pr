"""CSV importers — manual Kalodata/FastMoss exports are the Phase-1 data path."""

import pytest

from tt_engine.db import Database
from tt_engine.feeds import import_csv
from tt_engine.feeds.csv_import import slug_id


def _db(tmp_path):
    return Database(str(tmp_path / "csv.db"))


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_kalodata_style_export(tmp_path):
    path = _write(tmp_path, "kalo.csv", "\n".join([
        "Product Name,Category,Date,Sales Volume,Revenue,Sellers,Related Videos,Active Ads,Avg Ad Age",
        "Scalp Massager Pro,Beauty,2026-07-01,320,\"$4,480.00\",12,45,8,6",
        "Scalp Massager Pro,Beauty,2026-07-02,410,\"$5,740.00\",13,52,9,5",
    ]))
    with _db(tmp_path) as db:
        r = import_csv(db, path, source="kalodata")
        assert r.products == 1 and r.metric_rows == 2 and r.rows_skipped == 0
        pid = slug_id("Scalp Massager Pro")
        metrics = db.metrics_for(pid)
        assert len(metrics) == 2
        m = metrics[-1]
        # price derived from gmv/units; vendor $-and-comma formatting parsed.
        assert m.units == 410 and m.gmv == 5740.0 and m.price == 14.0
        assert m.sellers == 13 and m.promo_videos == 52 and m.ads == 9 and m.avg_ad_age == 5
        assert db.get_product(pid).category == "beauty"


def test_fastmoss_style_export_with_abbreviated_numbers(tmp_path):
    path = _write(tmp_path, "fm.csv", "\n".join([
        "Product,Stat Date,Daily Sales,Unit Price,Shop Count,Video Number",
        "LED Hoodie,07/01/2026,1.2k,29.99,25,110",
    ]))
    with _db(tmp_path) as db:
        r = import_csv(db, path, source="fastmoss")
        assert r.metric_rows == 1
        m = db.metrics_for(slug_id("LED Hoodie"))[0]
        assert m.units == 1200            # '1.2k' expanded
        assert m.date == "2026-07-01"     # MM/DD/YYYY parsed
        assert m.gmv == pytest.approx(1200 * 29.99)   # derived


def test_explicit_column_remap_and_unknown_field_rejected(tmp_path):
    path = _write(tmp_path, "odd.csv", "\n".join([
        "Item,When,Qty,Each",
        "Posture Corrector,2026-07-01,90,19.99",
    ]))
    with _db(tmp_path) as db:
        r = import_csv(db, path, column_map={
            "Item": "name", "When": "date", "Qty": "units", "Each": "price",
        })
        assert r.metric_rows == 1
        with pytest.raises(ValueError, match="unknown field"):
            import_csv(db, path, column_map={"Item": "nope"})


def test_bad_rows_skipped_with_reasons_not_silently(tmp_path):
    path = _write(tmp_path, "bad.csv", "\n".join([
        "Product Name,Date,Units,Price",
        "Good Product,2026-07-01,100,9.99",
        ",2026-07-01,50,9.99",                 # no name
        "No Numbers,2026-07-01,,",             # can't derive gmv/units/price
        "Bad Date,not-a-date,10,9.99",         # unparseable date
    ]))
    with _db(tmp_path) as db:
        r = import_csv(db, path)
        assert r.metric_rows == 1 and r.rows_skipped == 3
        assert len(r.skipped_reasons) == 3
        assert any("no product name" in s for s in r.skipped_reasons)
        assert any("unparseable date" in s for s in r.skipped_reasons)


def test_import_is_idempotent_and_logged(tmp_path):
    path = _write(tmp_path, "again.csv", "\n".join([
        "Product Name,Date,Units,Price",
        "Repeat Product,2026-07-01,100,9.99",
    ]))
    with _db(tmp_path) as db:
        import_csv(db, path, source="kalodata")
        import_csv(db, path, source="kalodata")  # same file again → upsert, not duplicate
        assert len(db.metrics_for(slug_id("Repeat Product"))) == 1
        history = db.import_history()
        assert len(history) == 2
        assert history[0]["source"] == "kalodata"
        assert history[0]["metric_rows"] == 1


def test_no_name_column_fails_loud(tmp_path):
    path = _write(tmp_path, "noname.csv", "col_a,col_b\n1,2\n")
    with _db(tmp_path) as db:
        with pytest.raises(ValueError, match="no product name"):
            import_csv(db, path)
