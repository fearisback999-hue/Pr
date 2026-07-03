"""Part 13 — The Feedback Loop (the moat).

The data feeds are rented and everyone can rent them. A scoring model tuned to your own
execution is the one asset competitors cannot buy. After 20–30 tested products, recalibrate
the Part-3 weights toward the sub-scores that actually predicted your winners."""

from .attribution import AttributionReport, ProductAttribution, attribute, render_monthly
from .recalibration import (
    MIN_SAMPLES,
    RecalibrationResult,
    label_winner,
    recalibrate,
)

__all__ = [
    "RecalibrationResult", "recalibrate", "label_winner", "MIN_SAMPLES",
    "attribute", "render_monthly", "AttributionReport", "ProductAttribution",
]
