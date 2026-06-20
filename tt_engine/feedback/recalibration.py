"""Recalibrate the Part-3 category weights from your own outcomes.

For each tested product we pair its six sub-scores (at scoring time) with a win/lose
label derived from real results (net margin, ROAS, decision). The point-biserial
correlation between each sub-score and the label tells us which sub-scores actually
predicted winners — and we nudge the weights toward those, renormalized to 100.

This is deliberately conservative: it needs a minimum sample, moves weights by a bounded
learning rate, and never lets a weight collapse to zero. The human still owns the call to
apply it (CLI `recalibrate --apply`)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ..db import Database, models
from ..scoring import DEFAULT_WEIGHTS, load_weights, save_weights

MIN_SAMPLES = 20         # Part 13: recalibrate after 20–30 tested products
LEARN_RATE = 0.5         # how hard to nudge weights toward predictive sub-scores
MIN_WEIGHT = 3.0         # never let a category collapse entirely

_CATEGORIES = list(DEFAULT_WEIGHTS.keys())


def label_winner(r: models.Result) -> Optional[int]:
    """1 = winner, 0 = loser, None = inconclusive (excluded from the fit)."""
    if r.decision == "scale":
        return 1
    if r.decision == "kill":
        return 0
    # Fall back to economics when no explicit decision.
    if r.net_margin is not None and r.roas is not None:
        return 1 if (r.net_margin > 0 and r.roas >= 1.5) else 0
    if r.net_margin is not None:
        return 1 if r.net_margin > 0 else 0
    return None


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else 0.0


@dataclass
class RecalibrationResult:
    applied: bool
    sample_size: int
    winners: int
    correlations: dict[str, float] = field(default_factory=dict)
    old_weights: dict[str, float] = field(default_factory=dict)
    new_weights: dict[str, float] = field(default_factory=dict)
    note: str = ""

    @property
    def summary(self) -> str:
        lines = [f"sample={self.sample_size} winners={self.winners} applied={self.applied}"]
        if self.note:
            lines.append(self.note)
        for c in _CATEGORIES:
            if c in self.new_weights:
                lines.append(
                    f"  {c:18s} corr {self.correlations.get(c, 0):+.2f}  "
                    f"{self.old_weights.get(c, 0):5.1f} → {self.new_weights[c]:5.1f}"
                )
        return "\n".join(lines)


def recalibrate(db: Database, apply: bool = False, min_samples: int = MIN_SAMPLES) -> RecalibrationResult:
    old = load_weights()

    # Pair each product's sub-scores with its win/lose label.
    rows: dict[str, tuple[models.Score, int]] = {}
    for r in db.all_results():
        label = label_winner(r)
        if label is None:
            continue
        score = db.latest_score(r.product_id)
        if score is None:
            continue
        rows[r.product_id] = (score, label)

    sample = list(rows.values())
    winners = sum(lbl for _, lbl in sample)

    if len(sample) < min_samples or winners == 0 or winners == len(sample):
        return RecalibrationResult(
            applied=False, sample_size=len(sample), winners=winners,
            old_weights=old, new_weights=old,
            note=(f"need ≥{min_samples} labeled products with both winners and losers "
                  f"(have {len(sample)}, {winners} winners) — keeping current weights"),
        )

    labels = [float(lbl) for _, lbl in sample]
    correlations: dict[str, float] = {}
    for cat in _CATEGORIES:
        vals = [float(getattr(s, cat)) for s, _ in sample]
        correlations[cat] = _pearson(vals, labels)

    # Nudge each weight by its correlation, floor it, renormalize to the original total.
    total_old = sum(old.values())
    raw = {c: max(MIN_WEIGHT, old[c] * (1 + LEARN_RATE * correlations[c])) for c in _CATEGORIES}
    scale = total_old / sum(raw.values())
    new = {c: round(raw[c] * scale, 2) for c in _CATEGORIES}

    if apply:
        save_weights(new)

    return RecalibrationResult(
        applied=apply, sample_size=len(sample), winners=winners,
        correlations=correlations, old_weights=old, new_weights=new,
        note=("applied — weights.json updated" if apply
              else "dry run — pass apply=True (CLI: --apply) to write weights.json"),
    )
