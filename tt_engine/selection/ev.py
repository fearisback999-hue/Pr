"""Expected-value ranking: pick tests by expected dollars, not points.

Two 84-scores are not equal bets. One is a $12 commodity at 48% margin with a
$6k/mo ceiling; the other a $40 niche product at 60% margin with a $35k/mo
ceiling. Same score band — wildly different payoff if they win. Ranking the test
queue by EV = p(win)·payoff − p(lose)·loss puts the money question first, which
is what "optimize for profit" actually means at the selection stage.

p(win) is a PRIOR, not a promise. It anchors on the researched disciplined-
beginner hit rate (~20%/test, the same constant the month-one calculator uses),
then shifts with score margin above the threshold, data confidence, and
lifecycle stage. It exists to ORDER the queue — the 48h kill timer, not this
number, decides what happens once money moves.

Refusals (the engine's standing invariants apply here too):
  • hard gates failed        → no EV; gates are absolute and EV never argues with them
  • below the score threshold → no EV; the queue ranks TEST-verdict products only
  • no landed cost on file    → no EV; expected dollars without real landed cost is fiction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..capital.month_one import TEST_BUDGET, WINNER_PROB
from ..config import CONFIG
from ..detection import LifecycleResult
from ..detection._stats import clamp
from ..scoring import ConfidenceResult
from ..scoring.algorithm import ScoreBreakdown
from .ceiling import CeilingEstimate

# A loser run with kill discipline recovers ~40% of its budget in revenue-side
# contribution before the 48h timer fires — you lose ~60% of the test budget.
# (Same arithmetic as the month-one calculator's loser leg: 0.8 ROAS × ~50% margin.)
LOSS_FRACTION = 0.60
# A winner's payoff window: ~90 days ramping toward its ceiling before fatigue —
# modeled as 1.5 ceiling-months of contribution (25% → 50% → 75% ramp). Heuristic.
PAYOFF_CEILING_MONTHS = 1.5

_LIFECYCLE_MULT = {
    "early_trend": 1.15,   # the whole point of the trigger: in before the crowd
    "growing": 1.0,
    "brand_new": 0.85,     # thin history — confidence already dings this, gently again
    "peaking": 0.60,       # late entries fund the peak
    "oversaturated": 0.40,
    "dead": 0.10,
}


def p_win(
    breakdown: ScoreBreakdown,
    confidence: ConfidenceResult,
    lifecycle: LifecycleResult,
) -> float:
    """Prior probability a funded test survives its 48h/break-even discipline."""
    if not breakdown.score.gates_passed:
        return 0.0
    edge = breakdown.score.total - CONFIG.score_threshold
    p = WINNER_PROB * (1.0 + 0.03 * edge)          # 80→0.20, 90→0.26, 95→0.29
    p *= clamp(0.6 + 0.5 * confidence.score, 0.6, 1.05)
    p *= _LIFECYCLE_MULT.get(lifecycle.stage, 1.0)
    return round(clamp(p, 0.02, 0.50), 3)


@dataclass
class EVResult:
    eligible: bool
    reason: str = ""                       # why ineligible (gates / threshold / unpriced)
    p_win: float = 0.0
    test_budget: float = TEST_BUDGET
    payoff_if_win: float = 0.0             # expected 90-day contribution if it works
    loss_if_lose: float = 0.0
    ev: Optional[float] = None             # p·payoff − (1−p)·loss ; None when ineligible

    @property
    def summary(self) -> str:
        if not self.eligible:
            return f"no EV — {self.reason}"
        return (f"EV ${self.ev:+,.0f} on a ${self.test_budget:.0f} test "
                f"(p(win) {self.p_win:.0%} × ${self.payoff_if_win:,.0f} payoff − "
                f"{1 - self.p_win:.0%} × ${self.loss_if_lose:.0f} loss)")


def expected_value(
    breakdown: ScoreBreakdown,
    confidence: ConfidenceResult,
    lifecycle: LifecycleResult,
    ceiling: CeilingEstimate,
    landed_known: bool,
    test_budget: float = TEST_BUDGET,
) -> EVResult:
    s = breakdown.score
    if not s.gates_passed:
        return EVResult(eligible=False,
                        reason="hard gate(s) failed: " + ", ".join(s.gate_failures))
    if s.total < CONFIG.score_threshold:
        return EVResult(eligible=False,
                        reason=f"total {s.total:.0f} < {CONFIG.score_threshold:.0f} — "
                               "not at TEST verdict")
    if not landed_known or ceiling.contribution_monthly is None:
        return EVResult(eligible=False,
                        reason="unpriced — no real landed cost on file; expected "
                               "dollars without landed cost is fiction (`add-supplier`)")

    p = p_win(breakdown, confidence, lifecycle)
    payoff = round(ceiling.contribution_monthly * PAYOFF_CEILING_MONTHS, 2)
    loss = round(test_budget * LOSS_FRACTION, 2)
    ev = round(p * payoff - (1.0 - p) * loss, 2)
    return EVResult(eligible=True, p_win=p, test_budget=test_budget,
                    payoff_if_win=payoff, loss_if_lose=loss, ev=ev)
