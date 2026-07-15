"""Month one: the initial cash you need, and the profit you should actually expect.

Every default below is a researched or engine-enforced number (2026-07, sources in the
playbook/OS doc), and every one is a parameter — override with your reality. The honest
headline this module refuses to soften: the EXPECTED value of month one is a small
loss. Month one buys data, reps, and the option on a winner — the beginner net-margin
band in the first 90 days is roughly −5% to +5%, and most tests lose by design
(kill discipline caps each loss; one winner pays for the field later).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Researched / engine defaults (each is a knob):
DATA_SUB = 40.0            # Kalodata-class analytics subscription, monthly
FORMATION = 0.0            # sole-prop start = $0; LLC later ($50–500 by state)
SAMPLE_COST = 18.0         # landed sample + shipped-to-you, typical $12–25
SAMPLES = 3                # sample everything before ad spend (SOP-4)
TESTS = 2                  # month-one realistic; engine's comfort floor is 3 concurrent
TEST_BUDGET = 200.0        # fixed per-product test budget ($150–300 band)
WINNER_PROB = 0.20         # honest per-test hit rate for a disciplined beginner
LOSER_ROAS = 0.8           # what a killed test typically recoups before the 48h timer
WINNER_ROAS = 2.2          # a modest month-one winner, just above a ~1.9 true break-even
TRUE_MARGIN = 0.50         # contribution margin before ad spend (true fee stack, §optimize)
PAYOUT_LAG_DAYS = 14.0     # TikTok holds payouts ~7–15 days → you front COGS meanwhile
CONTINGENCY = 0.15         # returns, reships, price surprises


@dataclass
class MonthOnePlan:
    # inputs
    tests: int
    test_budget: float
    samples: int
    sample_cost: float
    data_sub: float
    formation: float
    winner_prob: float
    loser_roas: float
    winner_roas: float
    true_margin: float
    # derived — cash
    fixed_costs: float
    sample_costs: float
    ad_budget: float
    cogs_float: float
    contingency: float
    initial_cash: float
    # derived — P&L scenarios (contribution after COGS/fees/ads, minus fixed)
    pnl_all_lose: float
    pnl_one_winner: float
    pnl_expected: float
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        lines = [
            "INITIAL CASH NEEDED (month one)",
            f"  data subscription        ${self.data_sub:>8.2f}",
            f"  business formation       ${self.formation:>8.2f}"
            + ("   (sole-prop start; LLC $50–500 later)" if self.formation == 0 else ""),
            f"  samples ({self.samples} × ${self.sample_cost:.0f})        ${self.sample_costs:>8.2f}",
            f"  ad tests ({self.tests} × ${self.test_budget:.0f})       ${self.ad_budget:>8.2f}",
            f"  COGS float (payout lag)  ${self.cogs_float:>8.2f}   (you pay suppliers ~"
            f"{PAYOUT_LAG_DAYS:.0f}d before TikTok pays you)",
            f"  contingency ({CONTINGENCY:.0%})        ${self.contingency:>8.2f}",
            f"  ─────────────────────────────────",
            f"  TOTAL                    ${self.initial_cash:>8.2f}",
            "",
            "EXPECTED PROFIT (contribution after all fees & ad spend, minus fixed costs)",
            f"  if every test loses (p≈{(1-self.winner_prob)**self.tests:.0%}):  "
            f"${self.pnl_all_lose:>8.2f}",
            f"  if one test wins:            ${self.pnl_one_winner:>8.2f}",
            f"  EXPECTED VALUE:              ${self.pnl_expected:>8.2f}",
        ]
        lines += [""] + [f"  • {n}" for n in self.notes]
        return "\n".join(lines)


def plan_month_one(
    tests: int = TESTS,
    test_budget: float = TEST_BUDGET,
    samples: int = SAMPLES,
    sample_cost: float = SAMPLE_COST,
    data_sub: float = DATA_SUB,
    formation: float = FORMATION,
    winner_prob: float = WINNER_PROB,
    loser_roas: float = LOSER_ROAS,
    winner_roas: float = WINNER_ROAS,
    true_margin: float = TRUE_MARGIN,
) -> MonthOnePlan:
    if tests < 1 or test_budget <= 0:
        raise ValueError("tests ≥ 1 and test_budget > 0")
    if not 0 < winner_prob < 1:
        raise ValueError("winner_prob must be in (0, 1)")
    if not 0 < true_margin <= 1:
        raise ValueError("true_margin must be in (0, 1]")

    fixed = data_sub + formation
    sample_costs = samples * sample_cost
    ad_budget = tests * test_budget

    # Per-test contribution = revenue × margin − ad spend  (margin already nets COGS+fees).
    loser_contrib = test_budget * loser_roas * true_margin - test_budget
    winner_contrib = test_budget * winner_roas * true_margin - test_budget

    # COGS float: suppliers are paid per order ~PAYOUT_LAG before TikTok settles. Size it
    # on the optimistic path (one winner's order volume) so a win can't cash-crunch you.
    winner_revenue = test_budget * winner_roas
    cogs_share = 1 - true_margin
    cogs_float = round(winner_revenue * cogs_share * (PAYOUT_LAG_DAYS / 30.0), 2)

    subtotal = fixed + sample_costs + ad_budget + cogs_float
    contingency = round(subtotal * CONTINGENCY, 2)
    initial_cash = round(subtotal + contingency, 2)

    pnl_all_lose = round(tests * loser_contrib - fixed, 2)
    pnl_one_winner = round((tests - 1) * loser_contrib + winner_contrib - fixed, 2)
    # Binomial EV over tests (each independently wins with winner_prob).
    ev_tests = tests * (winner_prob * winner_contrib + (1 - winner_prob) * loser_contrib)
    pnl_expected = round(ev_tests - fixed, 2)

    notes = [
        f"each killed test loses ~${-loser_contrib:.0f} (the 48h timer caps it — "
        f"recouping ~{loser_roas:.1f} ROAS at {true_margin:.0%} margin), not the full "
        f"${test_budget:.0f}",
        "the expected value is a LOSS on purpose: month one buys data, reps, and the "
        "option on a winner — the beginner net band in the first 90 days is −5%…+5%",
        "a winner's real payoff lands in months 2–3 when you scale it (this month it "
        "barely clears its own test spend)",
        "float/contingency are RESERVES, not spend — unspent, they roll into month two",
        f"defaults are researched 2026-07 knobs (samples ${SAMPLE_COST:.0f}, tests "
        f"${TEST_BUDGET:.0f}, winner rate {WINNER_PROB:.0%}) — replace with YOUR numbers "
        "as they become real; `capital` sizes the multi-month runway",
    ]

    return MonthOnePlan(
        tests=tests, test_budget=test_budget, samples=samples, sample_cost=sample_cost,
        data_sub=data_sub, formation=formation, winner_prob=winner_prob,
        loser_roas=loser_roas, winner_roas=winner_roas, true_margin=true_margin,
        fixed_costs=fixed, sample_costs=sample_costs, ad_budget=ad_budget,
        cogs_float=cogs_float, contingency=contingency, initial_cash=initial_cash,
        pnl_all_lose=pnl_all_lose, pnl_one_winner=pnl_one_winner,
        pnl_expected=pnl_expected, notes=notes,
    )
