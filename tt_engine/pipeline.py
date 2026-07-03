"""Orchestration (Part 12 agent loop): data-feed → DB → detection → economics → scoring
→ LLM enrichment → Higgsfield → report assembly. Each stage is independently callable so
you can run it by hand before trusting the cron (the iron rule of automation, Part 0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Optional

from .config import CONFIG
from .creative import HiggsfieldClient, build_kit
from .db import Database, models
from .detection import TriggerResult, evaluate
from .detection._stats import clamp
from .economics import Economics, compute_economics, unknown_economics
from .feeds import FeedRecord, get_feed
from .llm import LLMClient
from .psychology import PsychProfile, analyze, emotion_signal
from .reports.opportunity import AttackPacket, OpportunityReport, render_report
from .scoring import ContentSignals, ScoringInputs
from .scoring.algorithm import ScoreBreakdown, score_product
from .sourcing import SupplierScore, rank_suppliers

# Category return-risk priors (Part 6: anything with sizing is a refund machine).
_RETURN_RATE = {
    "beauty": 0.04, "wellness": 0.04, "supplement": 0.05, "apparel": 0.12,
    "toys": 0.05, "electronics": 0.05, "home": 0.06,
}


def return_rate_for(category: str) -> float:
    return _RETURN_RATE.get(category.lower(), 0.06)


# ── ingestion ───────────────────────────────────────────────────────────────────
def ingest(db: Database, feed=None, lookback: int = 35) -> list[FeedRecord]:
    feed = feed or get_feed(CONFIG.primary_feed)
    records = feed.fetch(lookback_days=lookback)
    for rec in records:
        # Persist the review corpus on the product so re-scoring is reproducible
        # (it feeds psychology + the Viral-Demonstration emotion signal).
        rec.product.reviews = rec.reviews
        db.upsert_product(rec.product)
        db.upsert_metrics(rec.metrics)
    return records


def economics_for(db: Database, product: models.Product, latest_price: float) -> Economics:
    """Use the best (lowest-landed) known supplier. If none is on file we REFUSE to guess
    (no placeholder landed costs — those numbers gate real money): economics comes back
    flagged `landed_known=False`, the Economics sub-score is withheld, and the margin gate
    fails as unverifiable. Return-risk is a category prior until you measure your own."""
    suppliers = db.suppliers_for(product.id)
    rr = return_rate_for(product.category)
    if suppliers:
        best = min(suppliers, key=lambda s: s.cost + s.ship_cost)
        return compute_economics(latest_price, best.cost, best.ship_cost, return_rate=rr)
    return unknown_economics(latest_price, return_rate=rr)


# ── scoring ─────────────────────────────────────────────────────────────────────
@dataclass
class ScoredRecord:
    record: FeedRecord
    trigger: TriggerResult
    economics: Economics
    breakdown: ScoreBreakdown


def score_record(db: Database, rec: FeedRecord) -> ScoredRecord:
    metrics = sorted(rec.metrics, key=lambda m: m.date)
    trigger = evaluate(metrics)
    latest_price = metrics[-1].price if metrics else 0.0
    econ = economics_for(db, rec.product, latest_price)

    # First-party signals: upstream-demand proxy from week-over-week growth, and a
    # review-emotion read feeding the Viral Demonstration sub-score (Part 3.1).
    trend_proxy = clamp(trigger.momentum.wow_growth, -0.3, 0.6)
    content = ContentSignals()
    sig = emotion_signal(rec.reviews)
    if sig is not None:
        content.curiosity_interrupt, content.emotional_reaction = sig
    inputs = ScoringInputs(
        product=rec.product, trigger=trigger, economics=econ,
        search_trend_slope=trend_proxy, content=content,
    )
    breakdown = score_product(inputs)
    return ScoredRecord(record=rec, trigger=trigger, economics=econ, breakdown=breakdown)


def score_stored(db: Database, product_id: str) -> Optional[ScoredRecord]:
    """Re-score a product from metrics already in the DB (no feed call). Reviews aren't
    persisted, so psychology is built separately when assembling a packet."""
    product = db.get_product(product_id)
    if product is None:
        return None
    metrics = db.metrics_for(product_id)
    if not metrics:
        return None
    # Reviews were persisted at ingest, so this reproduces the canonical score exactly.
    rec = FeedRecord(product=product, metrics=metrics, reviews=product.reviews)
    return score_record(db, rec)


# ── daily pass ──────────────────────────────────────────────────────────────────
@dataclass
class DailyResult:
    date: str
    scored: list[ScoredRecord] = field(default_factory=list)
    new_candidates: list[ScoredRecord] = field(default_factory=list)  # ≥ threshold AND gates pass

    @property
    def headline(self) -> str:
        triggered = sum(1 for s in self.scored if s.trigger.triggered)
        return (f"{len(self.scored)} products scored · {triggered} triggered · "
                f"{len(self.new_candidates)} attack-ready (≥{CONFIG.score_threshold:.0f} & gates pass)")


def daily(db: Database, feed=None, lookback: int = 35) -> DailyResult:
    records = ingest(db, feed, lookback)
    today = _date.today().isoformat()
    scored: list[ScoredRecord] = []
    candidates: list[ScoredRecord] = []
    for rec in records:
        sr = score_record(db, rec)
        db.upsert_score(sr.breakdown.score)
        scored.append(sr)
        if sr.breakdown.score.gates_passed and sr.breakdown.score.total >= CONFIG.score_threshold:
            candidates.append(sr)
    scored.sort(key=lambda s: s.breakdown.score.total, reverse=True)
    candidates.sort(key=lambda s: s.breakdown.score.total, reverse=True)
    return DailyResult(date=today, scored=scored, new_candidates=candidates)


# ── attack-packet assembly (the 70% the product isn't) ──────────────────────────
def build_attack_packet(
    db: Database, sr: ScoredRecord, llm: Optional[LLMClient] = None,
    push_creative: bool = True, build_creative: bool = True,
) -> AttackPacket:
    """Assemble the full packet for a candidate. `build_creative=False` skips the Higgsfield
    kit (finding ≠ producing creative) — used by `find_winners` for a fast ranked view."""
    llm = llm or LLMClient()
    product = sr.record.product

    psych: PsychProfile = analyze(product.name, sr.record.reviews, product.category, llm)

    suppliers = db.suppliers_for(product.id)
    supplier_score: Optional[SupplierScore] = rank_suppliers(suppliers)[0] if suppliers else None

    kit = None
    creatives = []
    if build_creative:
        kit = build_kit(product, psych, variations=30, llm=llm)
        if push_creative:
            hf = HiggsfieldClient()
            creatives = hf.plan(kit)  # offline plan; hf.push() once the API is wired
            for c in creatives:
                db.upsert_creative(c)

    return AttackPacket(
        product=product, breakdown=sr.breakdown, trigger=sr.trigger,
        economics=sr.economics, psych=psych, supplier=supplier_score,
        kit=kit, planned_creatives=len(creatives),
    )


# ── find winners (the core job: surface the best products to move on now) ───────
@dataclass
class WinnersResult:
    date: str
    source: str                              # which feed produced these
    winners: list[AttackPacket]              # attack-ready, ranked best-first
    near_misses: list[ScoreBreakdown]        # momentum present but blocked / below bar

    @property
    def headline(self) -> str:
        return (f"{len(self.winners)} winning product(s) found via '{self.source}' · "
                f"{len(self.near_misses)} near-miss(es)")


def find_winners(
    db: Database, feed=None, top: int = 5, llm: Optional[LLMClient] = None,
) -> WinnersResult:
    """Run detection + scoring over the configured feed and return the best attack-ready
    products, ranked, each with the 'why it wins' context (no creative kit — that's the
    next step). Near-misses surface what's blocking the runners-up."""
    llm = llm or LLMClient()
    source = (feed.name if feed is not None else CONFIG.primary_feed)
    result = daily(db, feed)

    winners = [
        build_attack_packet(db, sr, llm, build_creative=False)
        for sr in result.new_candidates[:top]
    ]
    near = [
        sr.breakdown for sr in result.scored
        if not (sr.breakdown.score.gates_passed
                and sr.breakdown.score.total >= CONFIG.score_threshold)
        and (sr.trigger.triggered or sr.breakdown.score.total >= 60)
    ]
    return WinnersResult(date=result.date, source=source, winners=winners, near_misses=near)


# ── Phase 2: creative production on TEST verdict ────────────────────────────────
def produce_creatives(
    db: Database, product_id: str, llm: Optional[LLMClient] = None,
    confirm: bool = False, variations: int = 30, force: bool = False, mcp=None,
):
    """The Phase-2 trigger: when a product hits TEST verdict (gates clear, ≥ threshold),
    build the brief (product + psychology paragraph + hooks) and run the Higgsfield MCP
    batch across formats. Refuses on non-TEST products unless force=True, and never
    generates for real without confirm=True (generation spends money)."""
    from .creative import build_kit as _build_kit, generate_batch

    llm = llm or LLMClient()
    sr = score_stored(db, product_id)
    if sr is None:
        raise ValueError(f"{product_id}: no stored metrics — import or add data first")
    if not sr.breakdown.recommended and not force:
        s = sr.breakdown.score
        why = ("hard gate(s) failed: " + ", ".join(s.gate_failures)) if not s.gates_passed \
            else f"total {s.total:.1f} < {CONFIG.score_threshold:.0f}"
        raise ValueError(
            f"{product_id} is not at TEST verdict ({why}). Creative production is gated "
            "on TEST — re-score after fixing the blocker, or pass --force to override."
        )
    product = sr.record.product
    psych = analyze(product.name, product.reviews, product.category, llm)
    kit = _build_kit(product, psych, variations=variations, llm=llm)
    return kit, generate_batch(db, kit, confirm=confirm, mcp=mcp)


# ── weekly pass ─────────────────────────────────────────────────────────────────
def weekly(
    db: Database, feed=None, out_dir: Optional[str] = None,
    llm: Optional[LLMClient] = None, push_creative: bool = True,
) -> OpportunityReport:
    llm = llm or LLMClient()
    result = daily(db, feed)
    report = OpportunityReport(date=result.date)

    for sr in result.new_candidates:
        report.packets.append(build_attack_packet(db, sr, llm, push_creative))

    # Watchlist: momentum present but blocked by a gate or below the bar.
    for sr in result.scored:
        s = sr.breakdown.score
        attack_ready = s.gates_passed and s.total >= CONFIG.score_threshold
        if not attack_ready and (sr.trigger.triggered or s.total >= 60):
            report.watchlist.append(sr.breakdown)

    if out_dir:
        _write_report(report, out_dir)
    return report


def _write_report(report: OpportunityReport, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"opportunity_{report.date}.md").write_text(render_report(report))
    # One brief file per attack-ready product, ready for Hermes Agent.
    for p in report.packets:
        if p.kit:
            (out / f"brief_{p.product.id}.md").write_text(p.kit.brief_text())
