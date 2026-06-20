from tt_engine.db import models
from tt_engine.sourcing import TARGET_SHIP_DAYS, rank_suppliers, score_supplier


def _supplier(ref, ship_days, us_wh, moq=50, cost=6.0, rating=4.5, notes="sample passed"):
    return models.Supplier(
        ref=ref, product_id="P", name=ref, cost=cost, ship_cost=1.0,
        ship_days=ship_days, moq=moq, us_warehouse=us_wh, rating=rating,
        response_hrs=8, quality_notes=notes,
    )


def test_fast_us_warehouse_beats_slow_overseas():
    fast = score_supplier(_supplier("fast", ship_days=4, us_wh=True))
    slow = score_supplier(_supplier("slow", ship_days=20, us_wh=False))
    assert fast.total > slow.total
    assert fast.shipping > slow.shipping


def test_sample_order_always_flagged():
    s = score_supplier(_supplier("x", ship_days=4, us_wh=True))
    assert any("SAMPLE ORDER" in f for f in s.flags)


def test_slow_shipping_flagged_against_target():
    s = score_supplier(_supplier("slow", ship_days=14, us_wh=False))
    assert any(f"{TARGET_SHIP_DAYS:.0f}d target" in f for f in s.flags)


def test_high_moq_flagged():
    s = score_supplier(_supplier("bulk", ship_days=5, us_wh=True, moq=500))
    assert any("MOQ" in f for f in s.flags)


def test_rank_orders_by_total():
    ranked = rank_suppliers([
        _supplier("slow", ship_days=18, us_wh=False),
        _supplier("fast", ship_days=4, us_wh=True),
    ])
    assert ranked[0].supplier.ref == "fast"
