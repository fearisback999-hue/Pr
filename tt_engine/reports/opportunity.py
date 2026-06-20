"""Attack packets and the weekly opportunity report (Appendix A board + the 70% the
product isn't). Pure rendering — the pipeline assembles the data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Optional

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
                f"**Creative kit** — {len(self.kit.hooks)} hooks, {len(self.kit.scripts)} scripts, "
                f"{self.planned_creatives} planned variations across {len(self.kit.formats)} formats ({comp})",
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


def render_report(report: OpportunityReport) -> str:
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
        out += ["# Attack packets (≥80 and all gates clear)", ""]
        out += [p.render() for p in report.packets]
    else:
        out += ["_No products cleared the 80+ bar AND all hard gates this pass._", ""]

    if report.watchlist:
        out += ["# Watchlist (momentum present, but blocked or below bar)", ""]
        for b in report.watchlist:
            why = ", ".join(b.score.gate_failures) if not b.score.gates_passed else f"score {b.score.total:.0f} < 80"
            out.append(f"- **{b.score.product_id}** — {b.score.total:.0f}/100 · "
                       f"~{b.score.window_days:.0f}d · blocked: {why}")
        out.append("")
    return "\n".join(out)


def render_board(scores: list[models.Score], threshold: float = 0.0) -> str:
    """Appendix A board: one row per product, ranked by total descending."""
    header = (
        f"{'PRODUCT':<22}{'TOTAL':>7}{'WINDOW':>9}{'GATES':>7}  VERDICT\n"
        + "-" * 70
    )
    rows = [header]
    for s in scores:
        verdict = "ATTACK" if (s.gates_passed and s.total >= 80) else (
            "watch" if s.gates_passed else "GATED")
        window = f"{s.window_days:.0f}d" if s.window_days is not None else "—"
        gates = "pass" if s.gates_passed else "FAIL"
        rows.append(f"{s.product_id:<22}{s.total:>7.0f}{window:>9}{gates:>7}  {verdict}")
    return "\n".join(rows)
