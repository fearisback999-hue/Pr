"""Extract the psychological driver from a product's review/comment corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..llm import LLMClient, LLMUnavailable

_SYSTEM = (
    "You are a direct-response ecommerce strategist. Given a product and a corpus of its "
    "real customer reviews/comments, extract the customer psychology that drives purchase. "
    "Identify the SINGLE clearest psychological reason the product moves — products with one "
    "sharp trigger convert harder than ones with five vague ones. Ground every field in the "
    "corpus; do not invent benefits the reviews don't support."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "emotional_trigger": {"type": "string"},
        "pain_point": {"type": "string"},
        "desire": {"type": "string"},
        "identity_appeal": {"type": "string"},
        "impulse_factor": {"type": "string"},
        "spine": {
            "type": "string",
            "description": "One paragraph: the single psychological reason this product moves.",
        },
    },
    "required": [
        "emotional_trigger", "pain_point", "desire",
        "identity_appeal", "impulse_factor", "spine",
    ],
    "additionalProperties": False,
}


@dataclass
class PsychProfile:
    emotional_trigger: str
    pain_point: str
    desire: str
    identity_appeal: str
    impulse_factor: str
    spine: str                       # the one-paragraph reason — feeds every creative brief
    source: str = "offline"          # "llm" or "offline"

    @property
    def summary(self) -> str:
        return self.spine


def analyze(
    product_name: str,
    reviews: list[str],
    category: str = "",
    llm: Optional[LLMClient] = None,
) -> PsychProfile:
    """LLM pass when available; deterministic heuristic fallback otherwise."""
    llm = llm or LLMClient()
    if llm.available and reviews:
        try:
            corpus = "\n".join(f"- {r}" for r in reviews[:50])
            user = (
                f"Product: {product_name} (category: {category or 'unknown'})\n\n"
                f"Customer reviews/comments:\n{corpus}\n\n"
                "Return the JSON profile."
            )
            data = llm.complete_json(_SYSTEM, user, _SCHEMA)
            return PsychProfile(
                emotional_trigger=data["emotional_trigger"], pain_point=data["pain_point"],
                desire=data["desire"], identity_appeal=data["identity_appeal"],
                impulse_factor=data["impulse_factor"], spine=data["spine"], source="llm",
            )
        except LLMUnavailable:
            pass  # fall through to offline heuristic
    return _offline(product_name, reviews, category)


# ── cheap first-party emotion signal (no LLM) ──────────────────────────────────
# Feeds the Viral Demonstration sub-score's "emotional reaction" / "curiosity" components
# (Part 3.1) straight from the review corpus — first-party signal, computed deterministically.
_EMOTION_TOKENS = (
    "omg", "insane", "crazy", "obsessed", "cannot believe", "can't believe", "love",
    "amazing", "melts", "tingles", "fights over", "head-turner", "everyone asked",
    "addicted", "!",
)


def emotion_signal(reviews: list[str]) -> Optional[tuple[float, float]]:
    """Return (curiosity, emotional_reaction) in 0..1 from review intensity, or None."""
    if not reviews:
        return None
    text = " ".join(reviews).lower()
    hits = sum(text.count(t) for t in _EMOTION_TOKENS)
    per_review = hits / max(len(reviews), 1)
    emotion = min(0.95, 0.45 + 0.30 * per_review)
    curiosity = min(0.90, 0.50 + 0.25 * per_review)
    return round(curiosity, 3), round(emotion, 3)


# ── deterministic fallback ─────────────────────────────────────────────────────
_TRIGGER_KEYWORDS = {
    "relief": ["headache", "tension", "stress", "pain", "relax", "sleep", "sore"],
    "social proof / status": ["everyone asked", "head-turner", "compliments", "where did you get"],
    "novelty / wow": ["insane", "crazy", "wow", "cannot believe", "obsessed", "head-turner"],
    "belonging / identity": ["rave", "festival", "concert", "family", "kid", "my whole"],
    "instant gratification": ["fast", "instantly", "right away", "melts", "tingles"],
}


def _offline(product_name: str, reviews: list[str], category: str) -> PsychProfile:
    blob = " ".join(reviews).lower()
    scored = {
        trig: sum(blob.count(k) for k in kws) for trig, kws in _TRIGGER_KEYWORDS.items()
    }
    trigger = max(scored, key=scored.get) if any(scored.values()) else "curiosity / novelty"
    pain = "an everyday frustration the product visibly removes"
    if any(w in blob for w in ("headache", "tension", "stress", "pain", "sleep")):
        pain = "physical discomfort / stress they want gone now"
    desire = "a fast, visible result they can feel or show off"
    identity = "fits how they want to be seen by their peers" if "asked" in blob or "rave" in blob \
        else "a small upgrade to daily life"
    impulse = "low price + instant, demonstrable payoff makes it an easy yes"
    spine = (
        f"{product_name} moves on **{trigger}**: buyers are reacting to {pain}, and the product "
        f"delivers {desire}. The purchase is impulsive — {impulse}. Lead every creative with that "
        f"single trigger rather than a feature list."
    )
    return PsychProfile(
        emotional_trigger=trigger, pain_point=pain, desire=desire,
        identity_appeal=identity, impulse_factor=impulse, spine=spine, source="offline",
    )
