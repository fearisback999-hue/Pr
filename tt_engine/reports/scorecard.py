"""Per-product markdown scorecard: every sub-score, the input data behind it, the gate
results, and a verdict. No black-box numbers — an operator reading this sees exactly why
the product scored what it did and what would change the call.

Verdict mapping (Phase 1 spec):
  KILL  — failed a hard gate (disqualified regardless of total; momentum never overrides)
  TEST  — gates clear AND total ≥ threshold (default 80)
  WATCH — gates clear but below the bar
"""

from __future__ import annotations

from typing import Optional

from ..config import CONFIG
from ..economics import FEE_RATE, MARGIN_FLOOR
from ..pipeline import ScoredRecord


def verdict(gates_passed: bool, total: float, threshold: Optional[float] = None) -> str:
    threshold = CONFIG.score_threshold if threshold is None else threshold
    if not gates_passed:
        return "KILL"
    return "TEST" if total >= threshold else "WATCH"


def render_scorecard(sr: ScoredRecord) -> str:
    b = sr.breakdown
    s = b.score
    m = sr.trigger.momentum
    sat = sr.trigger.saturation
    e = sr.economics
    v = verdict(s.gates_passed, s.total)

    lines = [
        f"# Scorecard — {sr.record.product.name} (`{s.product_id}`)",
        "",
        f"**Date:** {s.date} · **Total:** {s.total:.1f}/100 · **Verdict:** **{v}**",
        "",
    ]
    if v == "KILL":
        lines.append("> ⛔ Disqualified by hard gate(s) — total score is irrelevant. "
                     "A hot momentum score never overrides a compliance or economic gate.")
    elif v == "TEST":
        lines.append(f"> ✅ Gates clear and total ≥ {CONFIG.score_threshold:.0f} — "
                     f"ready for a live ad test (~{s.window_days:.0f} days of runway).")
    else:
        lines.append(f"> 👀 Gates clear but total below {CONFIG.score_threshold:.0f} — "
                     "keep on the watchlist; re-score as new daily metrics land.")

    # ── Hard gates (checked FIRST — short-circuit) ─────────────────────────────
    lines += ["", "## Hard gates (checked first)", ""]
    if s.gates_passed:
        lines.append(f"All gates clear: margin ≥ {MARGIN_FLOOR*100:.0f}%, return-risk OK, "
                     "not branded/trademarked, not a restricted TikTok category.")
    else:
        for f in s.gate_failures:
            lines.append(f"- ⛔ {f}")

    # ── Sub-scores with the work shown ─────────────────────────────────────────
    lines += ["", "## Sub-scores", "",
              "| Category | Points | Weight | Components |",
              "|---|---:|---:|---|"]
    for cat, pts in b.category_points.items():
        w = b.weights.get(cat, 0)
        comps = " · ".join(f"{name} {cp:.2f}" for name, cp in b.components[cat].items())
        lines.append(f"| {cat.replace('_', ' ')} | {pts:.1f} | {w:.0f} | {comps} |")
    lines.append(f"| **TOTAL** | **{s.total:.1f}** | **100** | |")

    # ── The data behind the numbers ────────────────────────────────────────────
    lines += [
        "", "## Input data",
        "",
        "### Momentum (7-day vs 30-day velocity)",
        f"- velocity: {m.velocity_7d:.1f} units/day (7d) vs {m.velocity_30d:.1f} (30d) "
        f"→ ratio ×{m.momentum_ratio:.2f}",
        f"- week-over-week growth: {m.wow_growth*100:+.0f}%",
        f"- slope (last 7d): {m.slope_recent:+.2f} units/day/day · "
        f"acceleration (slope₇ − slope₇ₚᵣᵢₒᵣ): {m.acceleration:+.2f} → "
        f"{'accelerating' if m.is_accelerating else 'flat/decelerating'}",
        "",
        "### Saturation index",
        f"- inputs: {sat.sellers} sellers · {sat.promo_videos} promo videos · "
        f"{sat.ads} ads · avg ad age {sat.avg_ad_age:.0f}d",
        f"- index: **{sat.index:.0f}/100** (0.4·sellers + 0.35·promos + 0.25·ads vs "
        f"crowded ceilings) · entrant rate {sat.entrant_rate*100:+.1f}%/day · "
        f"fresh-ad flood: {'yes' if sat.fresh_ads else 'no'}",
        "",
        "### Window estimate",
        f"- **~{s.window_days:.0f} days of runway** = days until the fastest-growing "
        f"competition driver (sellers/promos/ads, growing at {sat.entrant_rate*100:+.1f}%/day) "
        "hits its crowded ceiling" + (" — haircut ×0.6 applied for fresh-ad flood"
                                      if sat.fresh_ads else ""),
        "",
        "### Economics",
    ]
    if not e.landed_known:
        lines.append("- ⛔ **NOT SCORED — no real landed cost on file.** No placeholder "
                     "guesses: add a supplier (`add-supplier`) with the real quoted "
                     "cost + shipping, then re-score.")
    else:
        lines += [
            f"- landed cost: ${e.supplier_cost:.2f} unit + ${e.ship_cost:.2f} ship = "
            f"**${e.landed_cost:.2f}**",
            f"- TikTok fee: {e.fee_rate*100:.0f}% × ${e.sell_price:.2f} = ${e.fee:.2f}"
            + ("" if e.fee_rate == FEE_RATE else " (non-default rate)"),
            f"- gross profit: ${e.sell_price:.2f} − ${e.landed_cost:.2f} − ${e.fee:.2f} = "
            f"**${e.gross_profit:.2f}** → margin **{e.gross_margin*100:.0f}%** "
            f"(floor {MARGIN_FLOOR*100:.0f}%)",
            f"- break-even ROAS: ${e.sell_price:.2f} ÷ ${e.gross_profit:.2f} = "
            f"**{e.breakeven_roas:.2f}**",
            f"- max allowable CAC: **${e.max_cac:.2f}** (spend more per customer and you "
            "lose on every sale)",
        ]
        if e.return_rate is not None:
            lines.append(f"- return-risk prior: {e.return_rate*100:.0f}% → expected profit "
                         f"after returns ${e.profit_after_returns:.2f}")
    return "\n".join(lines) + "\n"
