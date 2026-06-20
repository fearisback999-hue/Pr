"""Part 13 — The Feedback Loop (the moat).

The data feeds are rented and everyone can rent them. A scoring model tuned to your own
execution is the one asset competitors cannot buy. After 20–30 tested products, recalibrate
the Part-3 weights toward the sub-scores that actually predicted your winners."""

from .recalibration import (
    RecalibrationResult,
    recalibrate,
    label_winner,
    MIN_SAMPLES,
)

__all__ = ["RecalibrationResult", "recalibrate", "label_winner", "MIN_SAMPLES"]
