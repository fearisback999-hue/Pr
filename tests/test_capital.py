from tt_engine.capital import MIN_CONCURRENT_TESTS, plan_capital


def test_well_capitalized_supports_many_tests():
    plan = plan_capital(capital=10_000, test_budget=300, daily_ad_spend=50, daily_cogs=30)
    assert plan.max_concurrent_tests >= MIN_CONCURRENT_TESTS
    assert not plan.undercapitalized
    assert plan.payout_float > 0  # float exists whenever there's daily outflow


def test_thin_capital_flags_undercapitalized():
    plan = plan_capital(capital=600, test_budget=300, daily_ad_spend=40, daily_cogs=20)
    assert plan.undercapitalized
    assert any("concurrent" in w or "runway" in w for w in plan.warnings)


def test_payout_float_is_lag_times_daily_outflow():
    plan = plan_capital(capital=5000, test_budget=300, payout_lag_days=10,
                        daily_ad_spend=50, daily_cogs=50)
    assert plan.payout_float == (50 + 50) * 10  # 1000 tied up in transit


def test_reserve_is_held_back():
    plan = plan_capital(capital=1000, test_budget=300)
    # 15% reserve held back, no daily outflow → deployable = 850.
    assert plan.reserve == 150
    assert plan.deployable == 850


def test_no_burn_means_infinite_runway():
    plan = plan_capital(capital=1000, test_budget=300)
    assert plan.runway_months == float("inf")
