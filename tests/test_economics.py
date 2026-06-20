from tt_engine.economics import MARGIN_FLOOR, Offer, apply_offer, compute_economics


def test_basic_unit_economics():
    e = compute_economics(sell_price=24.99, supplier_cost=6.0, ship_cost=1.5, return_rate=0.04)
    # fee = 6% of price
    assert round(e.fee, 2) == round(0.06 * 24.99, 2)
    assert round(e.landed_cost, 2) == 7.5
    assert round(e.gross_profit, 2) == round(24.99 - 7.5 - e.fee, 2)
    assert e.gross_margin > 0.55
    assert e.meets_floor
    # break-even ROAS and max CAC
    assert abs(e.breakeven_roas - e.sell_price / e.gross_profit) < 1e-6
    assert e.max_cac == e.gross_profit


def test_thin_margin_fails_floor():
    e = compute_economics(sell_price=6.49, supplier_cost=4.5, ship_cost=0.3)
    assert e.gross_margin < MARGIN_FLOOR
    assert not e.meets_floor


def test_negative_profit_breakeven_is_inf():
    e = compute_economics(sell_price=10.0, supplier_cost=11.0)
    assert e.gross_profit < 0
    assert e.breakeven_roas == float("inf")
    assert e.max_cac == 0.0


def test_offer_bundle_improves_basket_margin():
    base = compute_economics(sell_price=20.0, supplier_cost=6.0, ship_cost=2.0)
    bundled = apply_offer(
        Offer(bundle_qty=2, bundle_price=35.0, upsell_take_rate=0.2, upsell_margin=5.0),
        unit_sell_price=20.0, supplier_cost=6.0, ship_cost=2.0,
    )
    # Bundling 2 units at $35 keeps a healthy margin and the upsell adds profit.
    assert bundled.sell_price == 35.0
    assert bundled.gross_profit > base.gross_profit
