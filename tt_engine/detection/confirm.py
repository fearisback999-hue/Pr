"""Cross-confirm a trigger across two velocity sources (Part 2: "Stack two velocity sources
and cross-confirm before trusting a trigger"). A single rented feed can be wrong or lag;
requiring two independent sources to agree cuts false positives before you spend money."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..db import models
from .trigger import TriggerResult, evaluate


@dataclass
class CrossConfirmation:
    confirmed: bool                  # both sources independently triggered
    primary: TriggerResult
    secondary: TriggerResult
    agreement: bool                  # both sources agree (triggered or both not)
    note: str

    @property
    def window_days(self) -> float:
        """Be conservative — trust the shorter of the two runway estimates."""
        return min(self.primary.window_days, self.secondary.window_days)


def cross_confirm(primary: TriggerResult, secondary: TriggerResult) -> CrossConfirmation:
    confirmed = primary.triggered and secondary.triggered
    agreement = primary.triggered == secondary.triggered
    window = min(primary.window_days, secondary.window_days)
    if confirmed:
        note = f"confirmed by both sources · trust window ~{window:.0f}d"
    elif primary.triggered != secondary.triggered:
        note = "sources DISAGREE — do not trust a single-source trigger; re-check before spending"
    else:
        note = "neither source triggered"
    return CrossConfirmation(
        confirmed=confirmed, primary=primary, secondary=secondary,
        agreement=agreement, note=note,
    )


def confirm_metrics(
    primary_metrics: Sequence[models.DailyMetric],
    secondary_metrics: Sequence[models.DailyMetric],
) -> CrossConfirmation:
    """Convenience: run detection on each source's series, then cross-confirm."""
    return cross_confirm(evaluate(primary_metrics), evaluate(secondary_metrics))
