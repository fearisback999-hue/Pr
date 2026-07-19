"""Selection layer — the answer to "which product do I fund NEXT, and can these
products stack to a $100k month?"

The scoring layer (Part 3) grades products in isolation. This layer sits on top
and ranks them the way a capital allocator would:

  ceiling  — plausible monthly revenue ceiling for a new entrant (market size ×
             capture × lifecycle headroom), and how many such products a $100k
             month takes
  ev       — expected dollars per test: p(win)·payoff − p(lose)·loss, at the TRUE
             fee stack; gates/threshold/unpriced products are refused, never guessed

The board still shows the score — the score is the quality instrument. The test
QUEUE is ordered by EV, because two equal scores are rarely equal bets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..db import models
from ..detection import LifecycleResult, TriggerResult
from ..economics import Economics
from ..scoring import ConfidenceResult
from ..scoring.algorithm import ScoreBreakdown
from .ceiling import (
    TARGET_MONTH,
    WINNER_CEILING_MO,
    CeilingEstimate,
    estimate_ceiling,
)
from .ev import TEST_BUDGET, EVResult, expected_value, p_win

__all__ = [
    "CeilingEstimate", "estimate_ceiling", "TARGET_MONTH", "WINNER_CEILING_MO",
    "EVResult", "expected_value", "p_win", "TEST_BUDGET",
    "SelectionResult", "evaluate_candidate", "rank_for_test",
]


@dataclass
class SelectionResult:
    ceiling: CeilingEstimate
    ev: EVResult
    fit: Optional[object] = None      # creative.ai_creator.FitResult when product known

    @property
    def summary(self) -> str:
        return f"{self.ev.summary} · {self.ceiling.summary}"


def evaluate_candidate(
    metrics: Sequence[models.DailyMetric],
    trigger: TriggerResult,
    economics: Economics,
    breakdown: ScoreBreakdown,
    lifecycle: LifecycleResult,
    confidence: ConfidenceResult,
    test_budget: float = TEST_BUDGET,
    product: Optional[models.Product] = None,
    reviews: Optional[Sequence[str]] = None,
) -> SelectionResult:
    ceiling = estimate_ceiling(metrics, trigger, lifecycle, economics)
    # The store's distribution is an AI persona + Spark boosts, so selection tilts
    # toward products the persona can honestly sell (creative.ai_creator).
    fit = None
    if product is not None:
        from ..creative.ai_creator import ai_fit
        fit = ai_fit(product, reviews)
    ev = expected_value(breakdown, confidence, lifecycle, ceiling,
                        landed_known=economics.landed_known, test_budget=test_budget,
                        distribution_fit=fit.score if fit else None)
    return SelectionResult(ceiling=ceiling, ev=ev, fit=fit)


def rank_for_test(scored: Sequence) -> list:
    """Order ScoredRecords for the test queue: EV-ranked eligibles first, then the
    rest by ceiling then score (a big-but-blocked product stays visible with its
    blocker — sometimes the fix is one supplier quote away)."""
    def key(sr):
        sel = sr.selection
        if sel.ev.eligible and sel.ev.ev is not None:
            return (1, sel.ev.ev, sr.breakdown.score.total)
        return (0, sel.ceiling.ceiling_monthly, sr.breakdown.score.total)
    return sorted(scored, key=key, reverse=True)
