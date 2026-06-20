"""Attack packets and the weekly opportunity report (Appendix A board + the 70% the
product isn't). Pure rendering — the pipeline assembles the data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import CONFIG
from ..creative.brief import CreativeKit
from ..db import models
from ..detection import TriggerResult
from ..economics import Economics
from ..psychology import PsychProfile
from ..scoring.algorithm import ScoreBreakdown
from ..sourcing import SupplierScore


@dataclass
class AttackPacket:
    product: models.Product
    breakdown: ScoreBreakdown
    trigger: TriggerResult
    economics: Economics
    psych: PsychProfile
    supplier: Optional[SupplierScore] = None
    kit: Optional[CreativeKit] = None
    planned_creatives: int = 0

    def render(self) -> str:
        s = self.breakdown.score
        lines = [
            f"## {self.product.name}  —  {s.total:.0f}/100  ·  ~{self.trigger.window_days:.0f}d runway",
            "",
            f"_{self.trigger.headline}_",
            "",
            "**Score breakdown**",
        ]
        for cat, pts in self.breakdown.category_points.items():
            w = self.breakdown.weights.get(cat, 0)
            lines.append(f"- {cat.replace('_', ' ')}: {pts:.1f}/{w:.0f}")
        if not s.gates_passed:
            lines += ["", f"> ⛔ **Gate failures:** {', '.join(s.gate_failures)}"]
        lines += [
            "",
            "**Economics** — " + self.economics.summary,
            "",
            "**Psychology spine (lead every ad with this)**",
            self.psych.spine,
        ]
        if self.supplier:
            lines += ["", "**Sourcing** — " + self.supplier.summary]
        if self.kit:
            comp = "compliant" if self.kit.compliant else f"{len(self.kit.flagged)} compliance flags"
            lines += [
                "",
                f"**Creative kit** — {len(self.kit.hooks)} hooks, "
                f"{len(self.kit.scripts)} scripts, {self.planned_creatives} planned "
                f"variations across {len(self.kit.formats)} formats ({comp})",
            ]
        lines += [
            "",
            "**Next moves** — order a sample, confirm a sub-5-day fulfillment route, seed "
            "creators (write outreach by hand), then test a spread on small budgets watching "
            "3s view rate → CTR → ATC → ROAS.",
            "",
            "---",
        ]
        return "\n".join(lines)


@dataclass
class OpportunityReport:
    date: str
    packets: list[AttackPacket] = field(default_factory=list)        # recommended (≥80, gates pass)
    watchlist: list[ScoreBreakdown] = field(default_factory=list)    # triggered but gated/below bar

    @property
    def headline(self) -> str:
        return f"{len(self.packets)} attack-ready · {len(self.watchlist)} on watch"


def render_report(report: OpportunityReport, threshold: Optional[float] = None) -> str:
    bar = CONFIG.score_threshold if threshold is None else threshold
    out = [
        f"# TikTok Shop — Opportunity Report ({report.date})",
        "",
        f"**{report.headline}**",
        "",
        "> No system predicts winners. This ranks and times opportunities so you move "
        "before the window closes. Most products you test will lose money — that is "
        "structural. Test many, most fail, a few winners pay for the failures.",
        "",
    ]
    if report.packets:
        out += [f"# Attack packets (≥{bar:.0f} and all gates clear)", ""]
        out += [p.render() for p in report.packets]
    else:
        out += [f"_No products cleared the {bar:.0f}+ bar AND all hard gates this pass._", ""]

    if report.watchlist:
        out += ["# Watchlist (momentum present, but blocked or below bar)", ""]
        for b in report.watchlist:
            why = (", ".join(b.score.gate_failures) if not b.score.gates_passed
                   else f"score {b.score.total:.0f} < {bar:.0f}")
            out.append(f"- **{b.score.product_id}** — {b.score.total:.0f}/100 · "
                       f"~{b.score.window_days:.0f}d · blocked: {why}")
        out.append("")
    return "\n".join(out)


def window_band(days: Optional[float]) -> str:
    """Urgency band for a runway estimate — 'a winner is a signal caught in time' (Part 0)."""
    if days is None:
        return "—"
    if days < 7:
        return "🔥 closing — likely late"
    if days <= 30:
        return "✅ act now"
    return "⏳ early / slower burn"


def render_winners(
    winners: list[AttackPacket],
    near_misses: list["ScoreBreakdown"],
    source: str,
    date: str,
) -> str:
    """Concise ranked 'best winning products' view: what to move on now, and why."""
    out = [f"# Best winning products — {date}  (source: {source})", ""]
    if source == "mock":
        out += [
            "> ⚠️ Running on the **sample feed**. These are illustrative, not real market "
            "finds. Set a real velocity source (KALODATA_API_KEY / ECHOTIK_API_KEY) and "
            "`TT_PRIMARY_FEED` to find actual winners.",
            "",
        ]
    if not winners:
        out += ["No attack-ready winners this pass (none cleared the bar AND all gates).", ""]
    for i, p in enumerate(winners, 1):
        s = p.breakdown.score
        m = p.trigger.momentum
        e = p.economics
        out += [
            f"#{i}  {p.product.name}  —  {s.total:.0f}/100  ·  "
            f"{window_band(s.window_days)} (~{s.window_days:.0f}d runway)",
            f"    why:   momentum x{m.momentum_ratio:.2f}, WoW {m.wow_growth*100:+.0f}%, "
            f"accelerating; saturation {p.trigger.saturation.index:.0f}/100 with room",
            f"    money: {e.gross_margin*100:.0f}% margin · ${e.gross_profit:.2f} profit/unit · "
            f"break-even ROAS {e.breakeven_roas:.2f} · max CAC ${e.max_cac:.2f}",
            f"    pull:  {p.psych.spine.split('. ')[0]}.",
        ]
        if p.supplier:
            out.append(f"    source: {p.supplier.summary}")
        out += ["    next:  sample → lock a sub-5-day route → `packet "
                f"{p.product.id}` for the full creative kit.", ""]

    if near_misses:
        out += ["## Near-misses (momentum, but blocked or below bar)", ""]
        for b in near_misses:
            why = (", ".join(b.score.gate_failures) if not b.score.gates_passed
                   else f"score {b.score.total:.1f} below bar")
            out.append(f"- {b.score.product_id} ({b.score.total:.1f}/100): {why}")
        out.append("")
    return "\n".join(out)


def render_board(scores: list[models.Score], threshold: Optional[float] = None) -> str:
    """Appendix A board: one row per product, ranked by total descending."""
    bar = CONFIG.score_threshold if threshold is None else threshold
    header = (
        f"{'PRODUCT':<22}{'TOTAL':>7}{'WINDOW':>9}{'GATES':>7}  VERDICT\n"
        + "-" * 70
    )
    rows = [header]
    for s in scores:
        verdict = "ATTACK" if (s.gates_passed and s.total >= bar) else (
            "watch" if s.gates_passed else "GATED")
        window = f"{s.window_days:.0f}d" if s.window_days is not None else "—"
        gates = "pass" if s.gates_passed else "FAIL"
        rows.append(f"{s.product_id:<22}{s.total:>7.0f}{window:>9}{gates:>7}  {verdict}")
    return "\n".join(rows)
