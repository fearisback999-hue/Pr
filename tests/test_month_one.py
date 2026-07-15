"""Month-one calculator: the cash math must be exact and the profit expectation must
stay honest (negative EV at realistic inputs — no month-one hype)."""

import pytest

from tt_engine.capital import plan_month_one
from tt_engine.capital.month_one import CONTINGENCY, PAYOUT_LAG_DAYS


def test_cash_breakdown_is_exact():
    p = plan_month_one(tests=2, test_budget=200, samples=3, sample_cost=18,
                       data_sub=40, formation=0, winner_prob=0.2,
                       loser_roas=0.8, winner_roas=2.2, true_margin=0.5)
    assert p.fixed_costs == 40
    assert p.sample_costs == 54
    assert p.ad_budget == 400
    # float = winner revenue × cogs share × lag/30 = 440 × 0.5 × 14/30
    assert p.cogs_float == pytest.approx(440 * 0.5 * PAYOUT_LAG_DAYS / 30, abs=0.01)
    subtotal = 40 + 54 + 400 + p.cogs_float
    assert p.contingency == pytest.approx(subtotal * CONTINGENCY, abs=0.01)
    assert p.initial_cash == pytest.approx(subtotal + p.contingency, abs=0.01)


def test_pnl_scenarios_are_coherent():
    p = plan_month_one(tests=2, test_budget=200, winner_prob=0.2,
                       loser_roas=0.8, winner_roas=2.2, true_margin=0.5)
    # loser contribution: 200×0.8×0.5 − 200 = −120 ; winner: 200×2.2×0.5 − 200 = +20
    assert p.pnl_all_lose == pytest.approx(2 * -120 - 40)     # −280
    assert p.pnl_one_winner == pytest.approx(-120 + 20 - 40)  # −140
    assert p.pnl_all_lose < p.pnl_one_winner                  # a winner helps…
    assert p.pnl_one_winner < 0                               # …but month one still nets red
    # EV sits between the scenarios and stays negative at honest defaults.
    assert p.pnl_all_lose < p.pnl_expected < p.pnl_one_winner + 200
    assert p.pnl_expected < 0


def test_honesty_survives_in_the_summary():
    s = plan_month_one().summary
    assert "INITIAL CASH NEEDED" in s
    assert "EXPECTED VALUE" in s
    assert "LOSS on purpose" in s                # the framing can't be silently softened
    assert "months 2–3" in s                     # where the winner actually pays


def test_kill_discipline_caps_the_loss():
    p = plan_month_one(tests=1, test_budget=200, true_margin=0.5, loser_roas=0.8)
    # A killed test loses 120, not the full 200 — the 48h timer's recoup is modeled.
    assert p.pnl_all_lose == pytest.approx(-120 - p.fixed_costs)


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        plan_month_one(tests=0)
    with pytest.raises(ValueError):
        plan_month_one(winner_prob=1.5)
    with pytest.raises(ValueError):
        plan_month_one(true_margin=0)
