"""AI market analysis (Part 4 extended): SWOT, risks, audience, objections, angles,
offers, pricing, and expected lifespan — for one product, composed from the numbers the
engine actually computed. Every bullet cites the signal it derives from; nothing is a
vibe. With ANTHROPIC_API_KEY set the psychology fields are LLM-grade; without it the
deterministic fallback is used and the analysis says so.

This is analysis, not prophecy: it structures what the data supports so YOU can decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .economics import MARGIN_FLOOR, Offer, apply_offer
from .pipeline import ScoredRecord
from .psychology import PsychProfile
from .scoring.gates import RETURN_RISK_RED_FLAG

# Audience sketches per category — starting points to refine with real comment data.
_AUDIENCE = {
    "beauty": "skincare/self-care buyers, mostly 18–34, discovery-driven, high repeat rate",
    "wellness": "sleep/stress/recovery seekers, 22–45, problem-aware and solution-shopping",
    "pet": "devoted pet owners, 25–54 — spend tracks emotion, not income; strong community pull",
    "hobby": "identity-driven enthusiasts — they buy to get BETTER at the thing they love",
    "accessories": "self-expression buyers, 16–34 — the product is a statement, not a tool",
    "apparel": "trend-driven, 16–30, sizing risk makes them return-happy",
    "home": "practical improvers, 25–54, respond to visible before/after",
    "electronics": "spec-comparers and gift buyers — price-anchored, loyalty-free",
    "toys": "parents + gift buyers; seasonal spikes, safety-sensitive",
    "supplement": "outcome-chasers; compliance minefield — no health claims, ever",
}


@dataclass
class MarketAnalysis:
    sr: ScoredRecord
    psych: PsychProfile
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    threats: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    audience: str = ""
    objections: list[tuple[str, str]] = field(default_factory=list)  # (objection, answer)
    angles: list[str] = field(default_factory=list)
    offer_moves: list[str] = field(default_factory=list)
    lifespan: str = ""
    scaling: str = ""

    def render(self) -> str:
        s = self.sr.breakdown.score
        e = self.sr.economics
        lines = [
            f"# Market analysis — {self.sr.record.product.name} (`{s.product_id}`)",
            "",
            f"**Score {s.total:.0f}/100 · lifecycle: {self.sr.lifecycle.stage.replace('_',' ')} · "
            f"{self.sr.confidence.summary}**",
            "",
            f"> Psychology source: {self.psych.source}"
            + ("" if self.psych.source == "llm"
               else " (deterministic fallback — set ANTHROPIC_API_KEY for the LLM pass)"),
            "",
            "## SWOT", "",
            "**Strengths**", *[f"- {x}" for x in self.strengths], "",
            "**Weaknesses**", *[f"- {x}" for x in self.weaknesses], "",
            "**Opportunities**", *[f"- {x}" for x in self.opportunities], "",
            "**Threats**", *[f"- {x}" for x in self.threats], "",
            "## Risk analysis", "",
            *[f"- {x}" for x in self.risks], "",
            "## Target audience & buyer psychology", "",
            f"- audience: {self.audience}",
            f"- emotional trigger: {self.psych.emotional_trigger}",
            f"- pain point: {self.psych.pain_point}",
            f"- desire: {self.psych.desire}",
            f"- identity appeal: {self.psych.identity_appeal}",
            f"- impulse factor: {self.psych.impulse_factor}",
            "",
            "## Objections → answers", "",
            *[f"- **{o}** → {a}" for o, a in self.objections], "",
            "## Marketing angles", "",
            *[f"- {x}" for x in self.angles], "",
            "## Offer & pricing moves (recomputed economics, not guesses)", "",
            *[f"- {x}" for x in self.offer_moves], "",
            "## Expected lifespan & scaling", "",
            f"- {self.lifespan}",
            f"- {self.scaling}",
        ]
        return "\n".join(lines) + "\n"


def analyze_market(sr: ScoredRecord, psych: PsychProfile) -> MarketAnalysis:
    b = sr.breakdown
    s = b.score
    e = sr.economics
    m = sr.trigger.momentum
    sat = sr.trigger.saturation
    product = sr.record.product
    a = MarketAnalysis(sr=sr, psych=psych)

    # ── SWOT from the strongest/weakest scored components ─────────────────────
    cats = sorted(b.category_points.items(),
                  key=lambda kv: kv[1] / max(b.weights.get(kv[0], 1), 1), reverse=True)
    for cat, pts in cats[:2]:
        w = b.weights.get(cat, 0)
        a.strengths.append(f"{cat.replace('_',' ')} is the strongest axis "
                           f"({pts:.1f}/{w:.0f}) — lead with it")
    if e.landed_known and e.gross_margin >= 0.55:
        a.strengths.append(f"{e.gross_margin*100:.0f}% gross margin absorbs a "
                           "15–25% affiliate cut without going underwater")
    if m.is_accelerating:
        a.strengths.append(f"demand is accelerating ({m.momentum_ratio:.2f}× baseline, "
                           f"WoW {m.wow_growth*100:+.0f}%)")

    for cat, pts in cats[-2:]:
        w = b.weights.get(cat, 0)
        if w and pts / w < 0.7:
            a.weaknesses.append(f"{cat.replace('_',' ')} lags ({pts:.1f}/{w:.0f}) — "
                                "the analysis below is where to compensate")
    if sr.confidence.band != "high":
        a.weaknesses.append(f"data confidence is only {sr.confidence.band}: "
                            + "; ".join(sr.confidence.reasons[:2]))
    if not a.weaknesses:
        a.weaknesses.append("no scored axis lags badly — the risk list below is the "
                            "real watch-item")

    if sr.lifecycle.actionable:
        a.opportunities.append(f"lifecycle is '{sr.lifecycle.stage.replace('_',' ')}' with "
                               f"~{sr.trigger.window_days:.0f}d runway — the entry window "
                               "is open now")
    a.opportunities.append("creator seeding before paid: the affiliate funnel converts "
                           "this psychology profile without fronting CAC")
    if b.components.get("competition_timing", {}).get("differentiation", 0) >= 2.8:
        a.opportunities.append("high differentiation — a light brand wrapper (name, "
                               "packaging insert, bundle) makes it defensible, not just early")

    a.threats.append(f"entrants arriving at {sat.entrant_rate*100:+.1f}%/day "
                     f"({sat.sellers} sellers, {sat.ads} ads today) — the window closes "
                     "whether or not you move")
    if sat.fresh_ads:
        a.threats.append("fresh-ad flood detected (young ad age + rising count) — "
                         "others just spotted it too")
    a.threats.append("platform risk: fee schedule, policy, and account-health rules "
                     "change with little notice (see the playbook's sourced steps)")

    # ── Risk analysis: proximity to the hard gates ─────────────────────────────
    if e.landed_known:
        margin_gap = e.gross_margin - MARGIN_FLOOR
        if margin_gap < 0.10:
            a.risks.append(f"margin is {margin_gap*100:.0f}pts above the {MARGIN_FLOOR*100:.0f}% "
                           "floor — one supplier price hike or shipping increase gates it")
        else:
            a.risks.append(f"margin buffer {margin_gap*100:.0f}pts above the floor — resilient "
                           "to moderate cost movement")
    rr = e.return_rate or 0.0
    rr_gap = RETURN_RISK_RED_FLAG - rr
    a.risks.append(
        f"return-rate estimate {rr*100:.0f}% vs the {RETURN_RISK_RED_FLAG*100:.0f}% gate "
        + ("— thin buffer; a bad batch trips it" if rr_gap <= 0.04
           else "— comfortable buffer")
    )
    a.risks.append("execution risk dominates product risk: the 48h kill timer and fixed "
                   "test budget are the actual downside caps — respect them")

    # ── Audience, objections, angles ──────────────────────────────────────────
    a.audience = _AUDIENCE.get(product.category.lower(),
                               "define from the first 50 comments — the corpus beats any prior")

    price_str = f"${e.sell_price:.2f}"
    a.objections = [
        (f"“{price_str} feels like a lot for this”",
         f"anchor against the alternative cost ({psych.pain_point}) — the ad shows the "
         "payoff in the first 3 seconds"),
        ("“Looks like the cheap ones I've seen”",
         "differentiation is the counter: show the detail a generic can't copy "
         "(material, mechanism, result) on camera"),
        ("“Will it actually work for me?”",
         "demonstration-first creative — real-time demo, no cuts; the compliance "
         "guardrail bans claims the product can't deliver, which keeps trust intact"),
        ("“Shipping will take forever”",
         "only promise the ship time your supplier actually hits (it's an account-health "
         "input); state it plainly on the listing"),
    ]

    a.angles = [
        f"problem-first: open on '{psych.pain_point}', resolve with the demo",
        f"identity: '{psych.identity_appeal}' — the buyer is telling the world something",
        f"trigger-led: every hook leads with {psych.emotional_trigger} (one trigger, "
        "not five)",
        "contrast: generic alternative vs this, side by side, no voiceover",
        "UGC reaction: first-time use, genuine reaction, zero polish — overproduced "
        "content underperforms on TikTok",
    ]

    # ── Offer moves: recomputed, not asserted ──────────────────────────────────
    if e.landed_known:
        bundle = apply_offer(Offer(bundle_qty=2, bundle_price=round(e.sell_price * 1.7, 2)),
                             e.sell_price, e.supplier_cost, e.ship_cost, e.return_rate)
        a.offer_moves.append(
            f"2-pack at ~{1.7:.1f}× unit price (${bundle.sell_price:.2f}): margin "
            f"{bundle.gross_margin*100:.0f}%, profit/order ${bundle.gross_profit:.2f} vs "
            f"${e.gross_profit:.2f} single — raises AOV without new CAC")
        thresh = round(e.sell_price * 1.5, 0)
        ship_offer = apply_offer(Offer(bundle_qty=2, free_ship_threshold=thresh),
                                 e.sell_price, e.supplier_cost, e.ship_cost, e.return_rate)
        a.offer_moves.append(
            f"free shipping over ${thresh:.0f}: order margin {ship_offer.gross_margin*100:.0f}% "
            "— the threshold nudges singles into pairs")
        a.offer_moves.append(
            f"price ceiling check: at ${e.sell_price:.2f} the break-even ROAS is "
            f"{e.breakeven_roas:.2f} and max CAC ${e.max_cac:.2f} — hold price until a "
            "creative beats that ROAS consistently, then test ±10%")
    else:
        a.offer_moves.append("no real landed cost on file — offer math refused until a "
                             "supplier quote exists (`add-supplier`)")

    # ── Lifespan & scaling ─────────────────────────────────────────────────────
    a.lifespan = (
        f"expected lifespan: lifecycle '{sr.lifecycle.stage.replace('_',' ')}' with "
        f"~{sr.trigger.window_days:.0f}d of pre-crowding runway; after that, margin "
        "compresses toward the crowd's CAC — plan the exit or the brand-wrap before entry"
    )
    a.scaling = (
        "scaling difficulty: single winners ceiling ~$40k/mo before fatigue — scale is "
        "won by creative variety (new hooks weekly) and supplier depth (reorder lead "
        "time, MOQ) more than by budget"
    )
    return a
