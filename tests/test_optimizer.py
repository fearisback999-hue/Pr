"""Profit optimizer: true fee stack, honest offer sweep, leak detection. These numbers
gate real money — pin the math."""

import pytest

from tt_engine.db import models
from tt_engine.economics import (
    MARGIN_FLOOR,
    optimize_offer,
    true_economics,
)


def test_true_stack_math_is_exact():
    # $20 sell, $5 landed. 6% referral + 3% payment + 15% affiliate = 24% of price.
    te = true_economics(20.0, 4.0, 1.0, payment_rate=0.03, affiliate_rate=0.15)
    assert te.base.gross_margin == pytest.approx((20 - 5 - 1.2) / 20)      # 69% at 6%-only
    assert te.true_profit == pytest.approx(20 - 5 - 20 * 0.24, abs=0.01)   # $10.20
    assert te.true_margin == pytest.approx(0.51, abs=0.005)
    assert te.true_breakeven_roas == pytest.approx(20 / 10.20, abs=0.01)
    assert te.true_max_cac == te.true_profit


def test_true_stack_is_always_worse_than_base():
    te = true_economics(30.0, 8.0, 1.5, affiliate_rate=0.20)
    assert te.true_margin < te.base.gross_margin
    assert te.true_breakeven_roas > te.base.breakeven_roas


def test_optimizer_recommends_within_constraints():
    r = optimize_offer("P-X", sell_price=21.99, supplier_cost=4.0, ship_cost=1.0,
                       affiliate_rate=0.15)
    assert r.recommendation is not None
    assert r.recommendation.in_impulse_band
    assert r.recommendation.above_floor
    # It's the max-profit option among those inside the constraints.
    viable = [o for o in r.options if o.viable and o.in_impulse_band]
    assert r.recommendation.true_profit_per_order == max(
        o.true_profit_per_order for o in viable)


def test_optimizer_flags_options_outside_impulse_band():
    r = optimize_offer("P-X", sell_price=21.99, supplier_cost=4.0, ship_cost=1.0)
    three_pack = next(o for o in r.options if o.units == 3)
    assert not three_pack.in_impulse_band            # 2.4 × 21.99 = $52.78 > $50
    assert "impulse band" in three_pack.line


def test_optimizer_refuses_to_recommend_negative_margin():
    # Thin product: $10 sell, $6 landed — nothing survives the true stack + floor.
    r = optimize_offer("P-THIN", sell_price=10.0, supplier_cost=5.0, ship_cost=1.0,
                       affiliate_rate=0.20)
    assert r.recommendation is None
    assert "No offer structure clears" in r.render()


def test_gate_pass_but_true_stack_fail_is_the_headline_leak():
    # 48% margin at 6%-only (clears the 45% gate), but 15% affiliate + 3% payment
    # pushes it under the floor → THE BIG ONE leak fires.
    sell, cost, ship = 20.0, 8.2, 1.0
    te = true_economics(sell, cost, ship, affiliate_rate=0.15)
    assert te.base.gross_margin >= MARGIN_FLOOR > te.true_margin
    r = optimize_offer("P-EDGE", sell_price=sell, supplier_cost=cost, ship_cost=ship,
                       affiliate_rate=0.15)
    assert any("THE BIG ONE" in leak for leak in r.leaks)


def test_actuals_leak_compares_logged_roas_to_true_breakeven():
    tests = [models.Test(id="t1", creative_id="c", date="2026-07-01", spend=50, roas=1.5),
             models.Test(id="t2", creative_id="c", date="2026-07-02", spend=50, roas=1.7)]
    r = optimize_offer("P-X", sell_price=21.99, supplier_cost=4.0, ship_cost=1.0,
                       affiliate_rate=0.15, tests=tests)
    actual_line = next(leak for leak in r.leaks if "actuals" in leak)
    assert "blended ROAS 1.60" in actual_line
    assert "BELOW" in actual_line          # 1.60 < true break-even (~1.88)
    assert "paying to sell" in actual_line


def test_render_shows_all_the_work():
    r = optimize_offer("P-X", sell_price=21.99, supplier_cost=4.0, ship_cost=1.0)
    text = r.render()
    assert "True take-rate" in text
    assert "demand elasticity is NOT modeled" in text   # the honesty line
    assert "★" in text                                   # a recommendation is marked
    assert "settlement statement" in text                # payment-rate caveat present
