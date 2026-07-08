"""Etsy POD listing planner — the math gates real hours and real money."""

import pytest

from tt_engine.capital import plan_pod


def test_pod_math_shown_and_correct():
    # $1000/mo at $8 profit → 125 sales/mo; at 0.4 sales/listing → 313 listings.
    plan = plan_pod(target_monthly_profit=1000, profit_per_sale=8.0,
                    sales_per_listing_month=0.4, hours_per_week=10,
                    minutes_per_listing=30)
    assert plan.sales_needed_month == 125
    assert plan.listings_needed == 313
    assert plan.new_listings_needed == 313
    assert plan.weekly_capacity == 20          # 10h × 60 ÷ 30min
    # ramp pace ceil(313/8)=40 > capacity 20 → time-capped at 20/week
    assert plan.weekly_recommended == 20
    assert plan.weeks_to_target == pytest.approx(313 / 20)
    assert "313" in plan.summary and "20" in plan.summary


def test_pod_counts_existing_listings():
    plan = plan_pod(target_monthly_profit=100, profit_per_sale=10.0,
                    sales_per_listing_month=0.5, current_listings=15)
    assert plan.listings_needed == 20
    assert plan.new_listings_needed == 5


def test_pod_target_already_met():
    plan = plan_pod(target_monthly_profit=100, profit_per_sale=10.0,
                    sales_per_listing_month=0.5, current_listings=100)
    assert plan.new_listings_needed == 0
    assert plan.weekly_recommended == 0


def test_pod_refuses_nonsense_inputs():
    with pytest.raises(ValueError, match="profit_per_sale"):
        plan_pod(target_monthly_profit=1000, profit_per_sale=0)
    with pytest.raises(ValueError, match="sales_per_listing"):
        plan_pod(target_monthly_profit=1000, profit_per_sale=5, sales_per_listing_month=0)
