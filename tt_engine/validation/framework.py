"""The 30-day plan and the kill/scale decision logic.

Kill (ANY one, after meaningful spend):
  • CTR persistently far below ~1% with no improving trend
  • ROAS below break-even after the test budget, flat or declining
  • refund rate trending above ~5%
  • comment sentiment dominated by quality / expectation complaints

Scale (ALL together):
  • CTR comfortably above ~1–1.5%
  • ROAS holding above break-even with room
  • refund rate low and stable
  • at least one creative angle clearly outperforming (a winner to iterate on)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Optional, Sequence

from ..db import models
from ..detection._stats import slope

# Heuristic thresholds (Part 9). Recalibrate against your own outcomes.
KILL_CTR = 0.01          # ~1%
SCALE_CTR = 0.015        # ~1.5%
KILL_REFUND = 0.05       # ~5%
SCALE_REFUND = 0.03      # low and stable
MEANINGFUL_SPEND = 50.0  # per product before kill/scale calls mean anything

WEEK_PLAN = {
    1: "Research & selection — run the engine, shortlist 80+ that clear gates, order samples, confirm fulfillment route.",
    2: "Creative production — full Higgsfield batch (20+/product), set up listing/offer/tracking, line up creators.",
    3: "Testing — launch a spread on small per-ad-set budgets; watch 3s view rate → CTR → ATC → ROAS in that order.",
    4: "Scaling decision — cut losers, pour into winners, decide if the product earns a real launch.",
}


@dataclass
class TestSummary:
    product_id: str
    spend: float
    impressions: int
    avg_three_sec_vr: Optional[float]
    avg_ctr: Optional[float]
    ctr_trend: float                  # slope of CTR over time (improving if > 0)
    avg_atc: Optional[float]
    avg_roas: Optional[float]
    roas_trend: float
    best_creative_ctr: Optional[float]
    has_clear_winner: bool


@dataclass
class ValidationDecision:
    product_id: str
    decision: str                     # "kill" | "scale" | "watch"
    reasons: list[str] = field(default_factory=list)
    summary: TestSummary = None        # type: ignore[assignment]

    @property
    def headline(self) -> str:
        return f"[{self.decision.upper()}] {self.product_id}: " + "; ".join(self.reasons)


def summarize_tests(product_id: str, tests: Sequence[models.Test]) -> TestSummary:
    tests = sorted(tests, key=lambda t: t.date)
    spend = sum(t.spend for t in tests)
    impressions = sum(t.impressions for t in tests)
    ctrs = [t.ctr for t in tests if t.ctr is not None]
    roases = [t.roas for t in tests if t.roas is not None]
    tsvr = [t.three_sec_vr for t in tests if t.three_sec_vr is not None]
    atcs = [t.atc for t in tests if t.atc is not None]

    # "Clear winner": at least one creative's CTR clearly beats the field.
    by_creative: dict[str, list[float]] = {}
    for t in tests:
        if t.ctr is not None:
            by_creative.setdefault(t.creative_id, []).append(t.ctr)
    per_creative_ctr = {cid: mean(v) for cid, v in by_creative.items() if v}
    best = max(per_creative_ctr.values()) if per_creative_ctr else None
    field_avg = mean(per_creative_ctr.values()) if per_creative_ctr else None
    has_winner = bool(best and field_avg and best >= max(SCALE_CTR, field_avg * 1.3))

    return TestSummary(
        product_id=product_id, spend=spend, impressions=impressions,
        avg_three_sec_vr=mean(tsvr) if tsvr else None,
        avg_ctr=mean(ctrs) if ctrs else None,
        ctr_trend=slope(ctrs) if len(ctrs) >= 2 else 0.0,
        avg_atc=mean(atcs) if atcs else None,
        avg_roas=mean(roases) if roases else None,
        roas_trend=slope(roases) if len(roases) >= 2 else 0.0,
        best_creative_ctr=best, has_clear_winner=has_winner,
    )


def decide(
    summary: TestSummary,
    breakeven_roas: float,
    refund_rate: Optional[float] = None,
    sentiment_complaints: bool = False,
) -> ValidationDecision:
    reasons: list[str] = []

    if summary.spend < MEANINGFUL_SPEND:
        reasons.append(f"only ${summary.spend:.0f} spent (< ${MEANINGFUL_SPEND:.0f}) — keep testing")
        return ValidationDecision(summary.product_id, "watch", reasons, summary)

    # ── Kill conditions (any one) ──────────────────────────────────────────────
    kill: list[str] = []
    if summary.avg_ctr is not None and summary.avg_ctr < KILL_CTR and summary.ctr_trend <= 0:
        kill.append(f"CTR {summary.avg_ctr*100:.2f}% < {KILL_CTR*100:.0f}% and not improving")
    if (summary.avg_roas is not None and breakeven_roas != float("inf")
            and summary.avg_roas < breakeven_roas and summary.roas_trend <= 0):
        kill.append(f"ROAS {summary.avg_roas:.2f} below break-even {breakeven_roas:.2f}, flat/declining")
    if refund_rate is not None and refund_rate > KILL_REFUND:
        kill.append(f"refunds {refund_rate*100:.0f}% > {KILL_REFUND*100:.0f}%")
    if sentiment_complaints:
        kill.append("comment sentiment dominated by quality/expectation complaints")
    if kill:
        return ValidationDecision(summary.product_id, "kill", kill, summary)

    # ── Scale conditions (all together) ────────────────────────────────────────
    scale_ok = (
        summary.avg_ctr is not None and summary.avg_ctr >= SCALE_CTR
        and summary.avg_roas is not None and breakeven_roas != float("inf")
        and summary.avg_roas > breakeven_roas * 1.15
        and (refund_rate is None or refund_rate <= SCALE_REFUND)
        and summary.has_clear_winner
    )
    if scale_ok:
        reasons.append(
            f"CTR {summary.avg_ctr*100:.2f}% ≥ {SCALE_CTR*100:.1f}%, "
            f"ROAS {summary.avg_roas:.2f} > break-even with room, refunds stable, clear winner"
        )
        return ValidationDecision(summary.product_id, "scale", reasons, summary)

    # ── Otherwise keep watching, with the gap noted ───────────────────────────
    if summary.avg_ctr is not None and summary.avg_ctr < SCALE_CTR:
        reasons.append(f"CTR {summary.avg_ctr*100:.2f}% not yet at scale bar")
    if summary.avg_roas is not None and summary.avg_roas <= breakeven_roas * 1.15:
        reasons.append("ROAS not yet comfortably above break-even")
    if not summary.has_clear_winner:
        reasons.append("no clearly outperforming creative yet")
    return ValidationDecision(summary.product_id, "watch", reasons or ["mixed signals"], summary)
