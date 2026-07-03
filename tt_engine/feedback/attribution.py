"""Phase 2 feedback loop: after each test concludes, log which sub-scores predicted the
outcome and which didn't — then roll it up into a monthly recalibration report.

Attribution rule, per category: a sub-score "predicted a winner" when it was ≥ 60% of its
weight at scoring time. Cross that prediction with the real outcome:

                      product WON          product LOST
  sub-score high      hit (true positive)  miss (false positive)
  sub-score low       miss (false negative) hit (true negative)

The monthly report shows per-category hit-rates, the correlation fit, and the suggested
weight nudges. Suggestions ONLY — nothing is applied automatically; the operator applies
with `recalibrate --apply` after reading the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..db import Database
from ..scoring import load_weights
from .recalibration import label_winner, recalibrate

PREDICT_FRACTION = 0.60  # sub-score at/above 60% of its weight = "predicted a winner"

_CATEGORIES = ("viral_demo", "market_demand", "competition_timing",
               "economics", "content_potential", "brand_potential")


@dataclass
class ProductAttribution:
    product_id: str
    date: str                      # result date
    won: bool
    fractions: dict[str, float]    # category -> sub-score / weight at scoring time
    correct: dict[str, bool]       # category -> did that sub-score call this outcome?

    @property
    def line(self) -> str:
        outcome = "WIN " if self.won else "LOSS"
        marks = " ".join(
            f"{cat.split('_')[0]}:{'✓' if self.correct[cat] else '✗'}({self.fractions[cat]:.0%})"
            for cat in _CATEGORIES
        )
        return f"{self.product_id:<16} {outcome} {marks}"


@dataclass
class AttributionReport:
    rows: list[ProductAttribution] = field(default_factory=list)
    hit_rate: dict[str, float] = field(default_factory=dict)  # category -> fraction correct

    @property
    def sample_size(self) -> int:
        return len(self.rows)


def attribute(db: Database, month: Optional[str] = None) -> AttributionReport:
    """Pair every concluded result (optionally restricted to YYYY-MM) with its sub-scores
    and classify each category's prediction as hit or miss."""
    weights = load_weights()
    report = AttributionReport()

    for r in db.all_results():
        if month and not r.date.startswith(month):
            continue
        label = label_winner(r)
        if label is None:
            continue
        score = db.latest_score(r.product_id)
        if score is None:
            continue
        won = bool(label)
        fractions = {
            cat: (getattr(score, cat) / weights[cat] if weights.get(cat) else 0.0)
            for cat in _CATEGORIES
        }
        correct = {
            cat: (frac >= PREDICT_FRACTION) == won for cat, frac in fractions.items()
        }
        report.rows.append(ProductAttribution(
            product_id=r.product_id, date=r.date, won=won,
            fractions=fractions, correct=correct,
        ))

    if report.rows:
        report.hit_rate = {
            cat: sum(row.correct[cat] for row in report.rows) / len(report.rows)
            for cat in _CATEGORIES
        }
    return report


def render_monthly(db: Database, month: Optional[str] = None) -> str:
    """The monthly recalibration report (markdown). Suggestions only — the operator
    approves weight changes manually."""
    attr = attribute(db, month)
    recal = recalibrate(db, apply=False)   # dry-run fit over ALL labeled outcomes
    weights = load_weights()

    title = f"# Monthly recalibration report{f' — {month}' if month else ''}"
    lines = [title, ""]

    if not attr.rows:
        lines += [f"No concluded tests{f' in {month}' if month else ''} — log outcomes "
                  "with `log-result <id> --decision kill|scale` as tests conclude.", ""]
    else:
        wins = sum(r.won for r in attr.rows)
        lines += [
            f"**{attr.sample_size} concluded test(s)** — {wins} win(s), "
            f"{attr.sample_size - wins} loss(es).",
            "",
            "## Which sub-scores predicted the outcome",
            "",
            f"A sub-score 'predicted a winner' when ≥ {PREDICT_FRACTION:.0%} of its weight "
            "at scoring time. ✓ = it called this product's outcome; ✗ = it was wrong.",
            "",
            "```",
            *[row.line for row in attr.rows],
            "```",
            "",
            "| Category | Hit rate | Current weight |",
            "|---|---:|---:|",
            *[f"| {cat.replace('_', ' ')} | {attr.hit_rate[cat]:.0%} | {weights[cat]:.1f} |"
              for cat in _CATEGORIES],
            "",
        ]

    lines += ["## Suggested weight adjustments (correlation fit over all labeled outcomes)", ""]
    if recal.correlations:
        lines += [
            "| Category | Correlation with winning | Weight now | Suggested |",
            "|---|---:|---:|---:|",
            *[f"| {cat.replace('_', ' ')} | {recal.correlations[cat]:+.2f} "
              f"| {recal.old_weights[cat]:.1f} | {recal.new_weights[cat]:.1f} |"
              for cat in _CATEGORIES],
        ]
    else:
        lines.append(recal.note)
    lines += [
        "",
        "> **Suggestions only.** Nothing above was applied. Read it, sanity-check it "
        "against what you saw in the market, then apply manually with "
        "`python -m tt_engine.cli recalibrate --apply`.",
    ]
    return "\n".join(lines) + "\n"
