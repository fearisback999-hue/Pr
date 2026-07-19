"""AI-creator advertising: the persona is the ad engine — where that's honest.

The operator's strategy: a consistent, labeled AI persona (one Soul ID per store)
produces the advertising, with Spark boosts turning the best organic posts into the
paid test. This module optimizes product selection and planning for that lane.

Two ideas, one honesty line:

  FIT — not every winning product can be SOLD by an AI creator. A guitar strap's
  proof is in the hand: show it, turn it, wear it — an AI persona does that
  credibly. A calming vest's proof is a real dog settling; a pimple patch's proof
  is real skin clearing. Generating that footage is FABRICATING EVIDENCE — the
  AIGC label discloses the method, not that the depicted outcome never happened.
  Those products need real UGC/affiliate proof; the persona can still do
  talking-head, unboxing, and styling around it. `ai_fit` scores this and the EV
  queue tilts toward products the persona can actually carry.

  PLAN — the persona's advertising loop: post cadence, format mix from the
  creative pack, Spark boosts deploying the standard test budget on the best
  organic posts (same 48h kill discipline), and the lane economics that answer
  "why is the persona worth it": every persona-driven sale keeps the affiliate
  commission AND most of the CAC a cold paid ad would burn.

Deterministic, offline, no LLM required — priors + review-language reads, with
every heuristic stated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..capital.month_one import TEST_BUDGET
from ..config import CONFIG
from ..db import models
from ..economics import Economics
from ..economics.optimizer import DEFAULT_PAYMENT_RATE, true_economics
from .compliance import DISCLOSURE

# How credibly a labeled AI persona can deliver the WINNING demo, by category.
# High = the product itself is the proof (handle it on camera). Low = the proof
# is an outcome in the real world (body, skin, animal behavior) — fabricated-
# evidence territory for generated video, label or not.
_FIT_PRIOR = {
    "accessories": 0.85, "hobby": 0.85, "home": 0.80, "electronics": 0.80,
    "toys": 0.75, "apparel": 0.60,
    "pet": 0.45,          # the sale is the animal's reaction — that must be real
    "beauty": 0.25, "wellness": 0.25,
    "supplement": 0.15,   # outcome claims + health-claim compliance stack
}
_DEFAULT_PRIOR = 0.60

# Review language that says the purchase proof is an OUTCOME (must be real).
_OUTCOME_RE = re.compile(
    r"before.{0,15}after|transformation|cleared my|cured|faded|grew back"
    r"|results? (?:in|after|within)|lost \d+|pain (?:gone|relief|free)"
    r"|my (?:dog|cat|pet|baby|kid)s? .{0,40}(?:calm|stopped|slept|settl)"
    r"|(?:skin|acne|hair|wrinkle).{0,30}(?:clear|smooth|gone|improv)",
    re.IGNORECASE,
)
# Review language that says the proof is the OBJECT (an AI persona can show it).
_TACTILE_RE = re.compile(
    r"easy to (?:use|install|attach|clean)|looks (?:great|amazing|beautiful)"
    r"|quality feels|well[- ]made|sturdy|fits perfectly|snapped (?:on|in)"
    r"|love the (?:design|look|color|leather|texture)",
    re.IGNORECASE,
)

POSTS_PER_DAY = 2          # planning heuristic: sustainable persona cadence
BOOST_TOP_N = 2            # Spark-boost the best organic posts…
BOOST_DAYS = 2             # …for the standard 48h kill window
DEFAULT_AFFILIATE_RATE = 0.15


@dataclass
class FitResult:
    score: float                       # 0..1 — how much of the sale the persona can carry
    reasons: list[str] = field(default_factory=list)
    use_for: list[str] = field(default_factory=list)
    never_for: list[str] = field(default_factory=list)

    @property
    def band(self) -> str:
        if self.score >= 0.7:
            return "strong"
        if self.score >= 0.45:
            return "partial"
        return "poor"

    @property
    def summary(self) -> str:
        return (f"AI-creator fit {self.score:.0%} ({self.band}) — "
                + "; ".join(self.reasons))


def ai_fit(product: models.Product, reviews: Optional[Sequence[str]] = None) -> FitResult:
    """How much of this product's advertising a labeled AI persona can honestly carry."""
    reviews = list(reviews if reviews is not None else product.reviews or [])
    prior = _FIT_PRIOR.get(product.category.lower(), _DEFAULT_PRIOR)
    reasons = [f"category prior {prior:.0%} ({product.category or 'uncategorized'})"]

    score = prior
    if reviews:
        outcome_frac = sum(bool(_OUTCOME_RE.search(r)) for r in reviews) / len(reviews)
        tactile_frac = sum(bool(_TACTILE_RE.search(r)) for r in reviews) / len(reviews)
        if outcome_frac > 0:
            score -= 0.30 * outcome_frac
            reasons.append(f"buyers cite real-world OUTCOMES in {outcome_frac:.0%} of "
                           "reviews — that proof must be real footage")
        if tactile_frac > 0:
            score += 0.10 * tactile_frac
            reasons.append(f"buyers cite look/feel/handling in {tactile_frac:.0%} of "
                           "reviews — in-hand demo territory, persona-friendly")
    score = max(0.05, min(0.95, score))

    use_for = ["talking-head hooks and storytelling", "unboxing and in-hand demos",
               "styling / setup / how-to", "reply-to-comment posts"]
    never_for = ["fabricated customer testimonials",
                 "before/after or results claims (compliance sweep also blocks these)"]
    if score < 0.7:
        never_for.append(
            "outcome proof — a generated 'result' is fabricated evidence; the AIGC "
            "label discloses the method, not that the outcome never happened. Source "
            "outcome footage from real affiliate UGC; the persona frames it.")
    return FitResult(score=round(score, 3), reasons=reasons,
                     use_for=use_for, never_for=never_for)


@dataclass
class Lane:
    label: str
    profit_per_order: float
    note: str


@dataclass
class CreatorPlan:
    product_id: str
    fit: FitResult
    persona: str
    posts_per_day: int
    weekly_mix: list[str]
    spark: list[str]
    lanes: list[Lane] = field(default_factory=list)
    lane_note: str = ""

    def render(self) -> str:
        lines = [
            f"# AI-creator advertising plan — {self.product_id}",
            "",
            f"**{self.fit.summary}**",
            "",
            f"PERSONA: {self.persona}",
            f"CADENCE: {self.posts_per_day} posts/day (planning heuristic — consistency "
            "beats bursts; the account must read as a person, not an ad faucet)",
            "",
            "## Weekly format mix",
            *[f"- {m}" for m in self.weekly_mix],
            "",
            "## The persona may / may never",
            *[f"- USE FOR: {u}" for u in self.fit.use_for],
            *[f"- NEVER: {n}" for n in self.fit.never_for],
            "",
            "## Spark loop (how organic posts become the ad test)",
            *[f"- {s}" for s in self.spark],
            "",
            "## Lane economics (why the persona is worth the effort)",
        ]
        if self.lanes:
            lines += [f"- {ln.label}: ${ln.profit_per_order:.2f}/order — {ln.note}"
                      for ln in self.lanes]
        if self.lane_note:
            lines += ["", self.lane_note]
        lines += ["", f"DISCLOSURE (non-negotiable): {DISCLOSURE.split('.')[0]}. "
                  "Every persona post carries the AIGC label; export refuses without it."]
        return "\n".join(lines) + "\n"


def build_creator_plan(
    product: models.Product,
    economics: Economics,
    soul_id: str = "",
    reviews: Optional[Sequence[str]] = None,
    affiliate_rate: float = DEFAULT_AFFILIATE_RATE,
) -> CreatorPlan:
    fit = ai_fit(product, reviews)
    soul = soul_id or CONFIG.higgsfield_soul_id
    from .persona import load_persona
    bible = load_persona()
    if bible:
        persona = (f"{bible.name} — the store's recurring persona"
                   + (f" (Soul ID {soul})" if soul else " (Soul ID not set yet — "
                      "train it from her bible's photo checklist)")
                   + f"; bible: {bible.source_path} ({bible.summary})")
    else:
        persona = (f"the store's recurring persona (Soul ID {soul}) — same face, room, "
                   "wardrobe on every post" if soul else
                   "no creator bible or Soul ID yet — write docs/persona/CREATOR.md "
                   "(shipped template) and train the Soul ID from its photo checklist; "
                   "cast drift is an AI tell AND a brand leak")

    mix = [
        f"{POSTS_PER_DAY * 7 - 4} persona posts: hooks + in-hand demos from the "
        "creative pack (naturalism-v2 prompts, one setting per clip)",
        "2 reply-to-comment posts (highest trust format — answer a real question)",
        "2 slots for real affiliate UGC" + (
            " — REQUIRED here: this product's outcome proof must be real footage"
            if fit.band != "strong" else " (optional social proof on top)"),
    ]
    per_boost = TEST_BUDGET / (BOOST_TOP_N * BOOST_DAYS)
    spark = [
        f"post organically for 48h, then Spark-boost the top {BOOST_TOP_N} posts by "
        f"engagement at ${per_boost:.0f}/day for {BOOST_DAYS} days = the standard "
        f"${TEST_BUDGET:.0f} test budget",
        "same discipline as any test: `log-test` daily, `validate` decides at the "
        "true break-even ROAS, 48h below break-even = KILL",
        "a boosted post that dies organically usually dies boosted — boost winners, "
        "don't resuscitate losers",
    ]

    lanes: list[Lane] = []
    lane_note = ""
    if economics.landed_known:
        base = true_economics(economics.sell_price, economics.supplier_cost,
                              economics.ship_cost, DEFAULT_PAYMENT_RATE, 0.0)
        aff = true_economics(economics.sell_price, economics.supplier_cost,
                             economics.ship_cost, DEFAULT_PAYMENT_RATE, affiliate_rate)
        delta = base.true_profit - aff.true_profit
        lanes = [
            Lane("persona organic (Spark-assisted)", base.true_profit,
                 "no affiliate cut, CAC only on the boosted share — the fattest "
                 "margin the product has; reach must be earned, not assumed"),
            Lane("paid ads on persona creative", base.true_profit,
                 f"full CAC applies — ads must beat break-even ROAS "
                 f"{base.true_breakeven_roas:.2f}"),
            Lane(f"affiliate UGC ({affiliate_rate:.0%})", aff.true_profit,
                 f"pays ${delta:.2f}/order for real faces and real proof — the "
                 "right price on outcome products, pure cost on handling products"),
        ]
        lane_note = (f"Every persona-driven sale keeps the ${delta:.2f} affiliate cut. "
                     "The persona doesn't replace affiliates — it replaces the LOW-"
                     "proof share of the content calendar, and affiliates cover what "
                     "the persona must never fake.")
    else:
        lane_note = ("lane economics withheld — no real landed cost on file "
                     "(`add-supplier`); margin comparisons without landed cost "
                     "are fiction.")
    return CreatorPlan(product_id=product.id, fit=fit, persona=persona,
                       posts_per_day=POSTS_PER_DAY, weekly_mix=mix, spark=spark,
                       lanes=lanes, lane_note=lane_note)
