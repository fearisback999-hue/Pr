"""Confidence in a score — how much the underlying DATA can be trusted, stated with
reasons. A 85/100 product score on 9 days of single-source data with no real landed
cost is a very different bet from the same score on 35 days of clean, costed data.

This is deliberately separate from the product score itself: the score says how good
the opportunity looks; confidence says how much to trust that look. Low confidence
never silently drags the score down — it's surfaced next to it with the exact reasons,
so the operator decides whether to gather more data or bet anyway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ..db import models
from ..detection import TriggerResult
from ..economics import Economics

FULL_HISTORY_DAYS = 30      # at/above this, history depth stops being a concern
MIN_REVIEWS = 3             # below this the psychology/complaint reads are guesses


@dataclass
class ConfidenceResult:
    score: float                     # 0..1
    reasons: list[str] = field(default_factory=list)  # why it ISN'T 1.0 (empty = clean)

    @property
    def band(self) -> str:
        if self.score >= 0.8:
            return "high"
        if self.score >= 0.55:
            return "medium"
        return "low"

    @property
    def summary(self) -> str:
        head = f"confidence {self.score:.0%} ({self.band})"
        if self.reasons:
            head += " — " + "; ".join(self.reasons)
        return head


def compute_confidence(
    metrics: Sequence[models.DailyMetric],
    trigger: TriggerResult,
    economics: Economics,
    reviews: Sequence[str],
    cross_confirmed: bool = False,
) -> ConfidenceResult:
    """Each deduction is a concrete data-quality gap, stated. Multiplicative, so several
    small gaps compound the way they should."""
    score = 1.0
    reasons: list[str] = []

    days = len(metrics)
    if days < FULL_HISTORY_DAYS:
        # Linear penalty down to 0.4× at 7 days — momentum math needs a real series.
        factor = max(0.4, 0.4 + 0.6 * (days / FULL_HISTORY_DAYS))
        score *= factor
        reasons.append(f"only {days} day(s) of metrics (< {FULL_HISTORY_DAYS}) — "
                       "momentum/saturation reads are early")

    if not economics.landed_known:
        score *= 0.5
        reasons.append("no real landed cost on file — economics unscored, margin gate "
                       "unverifiable")

    if len(reviews) < MIN_REVIEWS:
        score *= 0.85
        reasons.append(f"only {len(reviews)} review(s) — psychology, complaint, and "
                       "commodity reads are near-blind")

    if trigger.momentum.spike_capped:
        score *= 0.9
        reasons.append("a single anomalous day was spike-capped this week — the trend "
                       "read leans on a corrected series")

    if trigger.momentum.consistency < 0.5:
        score *= 0.85
        reasons.append(f"noisy daily series (consistency "
                       f"{trigger.momentum.consistency:.2f}) — the trend line is loose")

    if not cross_confirmed:
        score *= 0.9
        reasons.append("single data source — not cross-confirmed against a second feed "
                       "(detection.cross_confirm)")

    return ConfidenceResult(score=round(score, 3), reasons=reasons)
