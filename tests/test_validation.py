from tt_engine.db import models
from tt_engine.validation import decide, hours_below_breakeven, summarize_tests


def _tests(ctrs, roases, spend_each=20.0):
    """One test row per (ctr, roas) pair, on consecutive dates, two creatives."""
    out = []
    for i, (ctr, roas) in enumerate(zip(ctrs, roases)):
        out.append(models.Test(
            id=f"T{i}", creative_id=f"C{i % 2}", date=f"2026-06-{i+1:02d}",
            spend=spend_each, impressions=1000, three_sec_vr=0.3,
            ctr=ctr, atc=0.04, cvr=0.02, roas=roas,
        ))
    return out


def test_watch_when_spend_too_low():
    tests = _tests([0.02], [2.0], spend_each=10.0)  # only $10 spent
    d = decide(summarize_tests("P", tests), breakeven_roas=1.6)
    assert d.decision == "watch"
    assert "keep testing" in " ".join(d.reasons)


def test_kill_on_low_ctr_not_improving():
    tests = _tests([0.006, 0.005, 0.005], [0.9, 0.8, 0.8])
    d = decide(summarize_tests("P", tests), breakeven_roas=1.6)
    assert d.decision == "kill"


def test_kill_on_high_refunds():
    tests = _tests([0.02, 0.021, 0.022], [2.0, 2.1, 2.2])
    d = decide(summarize_tests("P", tests), breakeven_roas=1.6, refund_rate=0.08)
    assert d.decision == "kill"
    assert any("refund" in r for r in d.reasons)


# ── the 48-hour hard timer ───────────────────────────────────────────────────────
def test_48h_timer_kills_even_when_trend_improving():
    """Below break-even for 2 consecutive days = 48h = KILL — an improving trend
    doesn't buy more time (that's the point of the hard timer)."""
    tests = _tests([0.02, 0.02, 0.02], [1.0, 1.2, 1.4], spend_each=25.0)  # rising, still < 1.6
    d = decide(summarize_tests("P", tests), breakeven_roas=1.6, tests=tests)
    assert d.decision == "kill"
    assert any("48h" in r for r in d.reasons)


def test_under_48h_below_breakeven_does_not_trip_timer():
    tests = _tests([0.02, 0.02], [2.0, 1.0], spend_each=30.0)  # only latest day below
    hours, detail = hours_below_breakeven(tests, 1.6)
    assert hours == 24.0
    assert "1 consecutive day" in detail
    d = decide(summarize_tests("P", tests), breakeven_roas=1.6, tests=tests)
    assert d.decision != "kill" or not any("48h" in r for r in d.reasons)


def test_timer_resets_when_latest_day_recovers():
    tests = _tests([0.02, 0.02, 0.02], [1.0, 1.0, 2.2], spend_each=25.0)
    hours, detail = hours_below_breakeven(tests, 1.6)
    assert hours == 0.0
    assert "≥ break-even" in detail


def test_timer_aggregates_spend_weighted_roas_per_day():
    # Two creatives the same day: 0.5 and 2.5 ROAS on equal spend → day ROAS 1.5 < 1.6.
    tests = [
        models.Test(id="a", creative_id="C0", date="2026-06-01", spend=20, roas=0.5),
        models.Test(id="b", creative_id="C1", date="2026-06-01", spend=20, roas=2.5),
        models.Test(id="c", creative_id="C0", date="2026-06-02", spend=20, roas=1.5),
    ]
    hours, _ = hours_below_breakeven(tests, 1.6)
    assert hours == 48.0


def test_timer_needs_consecutive_calendar_days():
    # Bad day, gap, bad day → runs don't join across the gap.
    tests = [
        models.Test(id="a", creative_id="C0", date="2026-06-01", spend=20, roas=1.0),
        models.Test(id="b", creative_id="C0", date="2026-06-03", spend=20, roas=1.0),
    ]
    hours, _ = hours_below_breakeven(tests, 1.6)
    assert hours == 24.0  # only the trailing day counts


def test_scale_when_all_signals_strong():
    # Creative C0 clearly outperforms C1 → a clear winner.
    tests = [
        models.Test(id="a", creative_id="C0", date="2026-06-01", spend=30, impressions=2000,
                    ctr=0.030, atc=0.06, cvr=0.03, roas=2.4),
        models.Test(id="b", creative_id="C0", date="2026-06-02", spend=30, impressions=2000,
                    ctr=0.032, atc=0.06, cvr=0.03, roas=2.6),
        models.Test(id="c", creative_id="C1", date="2026-06-01", spend=20, impressions=1500,
                    ctr=0.016, atc=0.04, cvr=0.02, roas=1.9),
    ]
    d = decide(summarize_tests("P", tests), breakeven_roas=1.6, refund_rate=0.02)
    assert d.decision == "scale"
    assert d.summary.has_clear_winner
