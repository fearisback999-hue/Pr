"""The full creative pack (Part 7 extended): 50 hooks, 50 UGC concepts, 20 paid + 20
organic scripts, CTA variations, captions, hashtags, storyboards, voiceover lines,
B-roll and thumbnail ideas — one command, one document, every line compliance-swept.

Deterministic offline (templates × the product's real psychology profile); LLM-elevated
when ANTHROPIC_API_KEY is set. Volume is cheap — judgment isn't: the pack is raw material
for YOUR edit, not 160 things to ship blindly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..db import models
from ..llm import LLMClient
from ..psychology import PsychProfile
from .compliance import DISCLOSURE, ComplianceReport, review_text
from .hooks import Hook, generate_hooks
from .scripts import UGCScript, generate_scripts

# ── UGC concepts: scenario × angle, filled from the psych profile ───────────────
_SCENARIOS = [
    "Unboxing with zero commentary — let the product speak",
    "Day-in-the-life where the product solves {pain} mid-video",
    "Before/after split screen, same lighting, no cuts",
    "First-time reaction, filmed by a friend",
    "POV: your {audience_word} discovers it in your room",
    "3 things I didn't expect about it",
    "Replying to a hater comment with a live demo",
    "The 'I bought it so you don't have to' review",
    "Speed-run: problem to solved in under 15 seconds",
    "Comparison: the generic one vs this one, side by side",
    "ASMR: just the sounds of using it, close mic",
    "Storytime voiceover over b-roll of the product in use",
    "Duet-bait: 'show me yours' challenge format",
    "Gift reveal: filming their genuine reaction",
]
_ANGLES = ["played for {trigger}", "angled at '{desire}'",
           "opening on '{pain}'", "as identity content ({identity})"]


@dataclass
class UGCConcept:
    text: str
    scenario: str


def ugc_concepts(product: models.Product, psych: PsychProfile, n: int = 50) -> list[UGCConcept]:
    short = product.name.split("(")[0].strip()
    pain = " ".join(psych.pain_point.split()[:5])
    fills = {
        "pain": pain, "trigger": psych.emotional_trigger,
        "desire": " ".join(psych.desire.split()[:6]),
        "identity": " ".join(psych.identity_appeal.split()[:6]),
        "audience_word": "friend",
    }
    out: list[UGCConcept] = []
    for scenario in _SCENARIOS:
        base = scenario.format(**fills)
        for angle in _ANGLES:
            text = f"{base} — {angle.format(**fills)} ({short})"
            out.append(UGCConcept(text=text, scenario=base))
            if len(out) >= n:
                return out
    return out


# ── CTA variations ───────────────────────────────────────────────────────────────
_PAID_CTAS = [
    "Tap the orange cart before it sells out.",
    "Grab yours from the link — stock is moving.",
    "The cart button is right there. You know what to do.",
    "Get it now — link on screen.",
    "Orange cart. Two taps. Done.",
    "Check the cart for today's price.",
    "It's in the shop tab — go look.",
    "Tap the product link before you scroll past this.",
    "Add to cart now, thank yourself later.",
    "The link's below. Future you says thanks.",
]
_ORGANIC_CTAS = [
    "It's linked in my shop if you're curious.",
    "Comment 'link' and I'll reply.",
    "Save this for when you need it.",
    "Follow for the one-week update.",
    "Send this to someone who needs it.",
    "It's in my showcase — no pressure.",
    "Part 2 tomorrow if this hits 1k saves.",
    "Duet me with yours when it arrives.",
    "Genuinely just sharing — find it in my shop tab.",
    "Bookmark this. You'll want it later.",
]


def cta_variations(n: int = 20) -> list[str]:
    out = list(_PAID_CTAS) + list(_ORGANIC_CTAS)
    return out[:n]


# ── captions + hashtags ─────────────────────────────────────────────────────────
_CAPTION_TEMPLATES = [
    "I was today years old when I found the {name}",
    "The {name} understood the assignment",
    "Not me buying a {name} at 2am… no regrets",
    "{pain}? Not anymore.",
    "My {trigger} purchase of the year",
    "If you know, you know. {name}.",
    "This is your sign to fix {pain}",
    "Adding the {name} to your cart is self-care",
    "The {name} review nobody asked for (you're welcome)",
    "POV: the {name} actually delivered",
    "Day 7 with the {name}. Still obsessed.",
    "Normalize solving {pain} in 30 seconds",
    "The {name} > everything else I tried",
    "Tell me you have a {name} without telling me",
    "Me gatekeeping the {name}: not anymore",
    "It's the {name} for me",
    "Rating my {name}: 10/10 would panic-buy again",
    "The {name} was NOT supposed to be this good",
    "Little-known {name}, big difference",
    "Started as an impulse buy. Now it's a lifestyle. {name}.",
]


def captions(product: models.Product, psych: PsychProfile, n: int = 20) -> list[str]:
    short = product.name.split("(")[0].strip()
    pain = " ".join(psych.pain_point.split()[:5])
    return [t.format(name=short, pain=pain, trigger=psych.emotional_trigger)
            for t in _CAPTION_TEMPLATES[:n]]


def hashtags(product: models.Product, n: int = 12) -> list[str]:
    """Core discovery tags + tags derived from the product's own words. TikTok favors a
    small, relevant set over 30 spammy ones."""
    core = ["tiktokshop", "tiktokmademebuyit", "tiktokfinds", "fyp"]
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", product.name)][:4]
    cat = re.sub(r"[^a-z]", "", product.category.lower())
    derived = ["".join(words[:2])] if len(words) >= 2 else []
    tags = core + words + derived + ([cat] if cat else [])
    seen: list[str] = []
    for t in tags:
        if t and t not in seen:
            seen.append(t)
    return [f"#{t}" for t in seen[:n]]


# ── storyboard / voiceover / b-roll / thumbnails ────────────────────────────────
def storyboard(script: UGCScript) -> list[str]:
    """Scene-by-scene breakdown of one script, in shootable order."""
    return [
        f"SCENE 1 (0–3s) — HOOK: {script.first_3s} · framing: face + product in frame, "
        "text overlay of the hook, cut on the beat",
        f"SCENE 2 (3–8s) — SETUP: show the problem state for '{script.emotion}' — no "
        "talking needed, let it read",
        f"SCENE 3 (8–20s) — DEMO: {script.middle} · one continuous take; hands visible; "
        "natural light",
        "SCENE 4 (20–25s) — RESULT: hold on the outcome for 2 full seconds; this is the "
        "screenshot moment",
        f"SCENE 5 (25–30s) — CTA: {script.cta} · point at the cart/link; end card with "
        "the product name",
    ]


def voiceover_lines(product: models.Product, psych: PsychProfile, n: int = 8) -> list[str]:
    short = product.name.split("(")[0].strip()
    return [
        f"Okay so I finally tried the {short} everyone's talking about.",
        f"If {psych.pain_point.split(',')[0].lower()} is your daily reality — watch this.",
        "No script, no cuts. Just watch what happens.",
        f"This is the part that got me — {psych.desire.split(',')[0].lower()}.",
        "I genuinely didn't expect it to work this fast.",
        f"It's the {psych.emotional_trigger} for me.",
        "You can see the difference. I'm not narrating it — look.",
        "Anyway. It's in my shop tab. Do with that what you will.",
    ][:n]


def broll_ideas(product: models.Product) -> list[str]:
    short = product.name.split("(")[0].strip()
    return [
        f"macro close-up of the {short}'s texture/material, slow pan",
        "hands opening the package, first touch",
        "the product in its real use environment, wide shot",
        "slow-motion of the key action/mechanism",
        "over-the-shoulder POV of actual use",
        "the 'after' state held steady for 3 seconds",
        "product on a clean surface, one light source, rotating",
        "reaction shot — eyes only, then reveal what they're looking at",
    ]


def thumbnail_ideas(product: models.Product) -> list[str]:
    short = product.name.split("(")[0].strip()
    return [
        f"split-frame before/after with the {short} centered",
        "mid-reaction face + product held to camera, high contrast",
        "the result close-up with a 3-word overlay",
        "hand holding the product toward lens, shallow depth",
        "text-led: the hook's first 5 words, product small in corner",
    ]


# ── the pack ────────────────────────────────────────────────────────────────────
@dataclass
class CreativePack:
    product: models.Product
    psych: PsychProfile
    hooks: list[Hook]
    concepts: list[UGCConcept]
    paid_scripts: list[UGCScript]
    organic_scripts: list[UGCScript]
    ctas: list[str]
    caption_list: list[str]
    tag_list: list[str]
    voiceover: list[str]
    broll: list[str]
    thumbnails: list[str]
    realism_prompts: list = field(default_factory=list)   # RealismPrompt (naturalism layer)
    compliance: list[ComplianceReport] = field(default_factory=list)

    @property
    def flagged(self) -> list[ComplianceReport]:
        return [c for c in self.compliance if not c.ok]

    def render(self) -> str:
        lines = [
            f"# Creative pack — {self.product.name}",
            "",
            f"> Psychological spine (lead EVERYTHING with this): {self.psych.spine}",
            "",
            f"> {DISCLOSURE}",
            "",
            f"## Hooks ({len(self.hooks)})", "",
            *[f"- [{h.type}] {h.text}" for h in self.hooks], "",
            f"## UGC concepts ({len(self.concepts)})", "",
            *[f"- {c.text}" for c in self.concepts], "",
            f"## Paid ad scripts ({len(self.paid_scripts)})", "",
        ]
        for i, s in enumerate(self.paid_scripts, 1):
            lines += [f"**Paid {i} — targets {s.emotion}**",
                      f"- 0–3s: {s.first_3s}", f"- middle: {s.middle}",
                      f"- CTA: {s.cta}", ""]
        lines += [f"## Organic scripts ({len(self.organic_scripts)})", ""]
        for i, s in enumerate(self.organic_scripts, 1):
            lines += [f"**Organic {i} — targets {s.emotion}**",
                      f"- 0–3s: {s.first_3s}", f"- middle: {s.middle}",
                      f"- CTA: {s.cta}", ""]
        if self.realism_prompts:
            lines += [f"## Higgsfield prompts — naturalism-enhanced "
                      f"({len(self.realism_prompts)})", "",
                      "Phone-real, not cinematic: labeled AI content that FEELS native "
                      "performs; over-polish reads as an ad. The disclosure stays on — "
                      "craft and honesty are compatible.", ""]
            for i, rp in enumerate(self.realism_prompts, 1):
                lines += [f"**Prompt {i}**", "```", rp.render(), "```", ""]
            from .realism import render_qa_checklist
            lines += [render_qa_checklist(), ""]
        lines += [
            f"## CTA variations ({len(self.ctas)})", "",
            *[f"- {c}" for c in self.ctas], "",
            f"## Captions ({len(self.caption_list)})", "",
            *[f"- {c}" for c in self.caption_list], "",
            "## Hashtags", "", " ".join(self.tag_list), "",
            "## Voiceover lines", "", *[f"- {v}" for v in self.voiceover], "",
            "## B-roll shot list", "", *[f"- {b}" for b in self.broll], "",
            "## Thumbnail ideas", "", *[f"- {t}" for t in self.thumbnails], "",
            "## Storyboard (first paid script)", "",
        ]
        if self.paid_scripts:
            lines += [f"- {s}" for s in storyboard(self.paid_scripts[0])]
        if self.flagged:
            lines += ["", "## ⚠️ Compliance flags — rewrite before use", ""]
            lines += [f"- {c.summary} → \"{c.text}\"" for c in self.flagged]
        else:
            lines += ["", "_Compliance sweep: clean (AI-content disclosure still required)._"]
        return "\n".join(lines) + "\n"


def _soften_for_organic(s: UGCScript, i: int) -> UGCScript:
    return UGCScript(hook=s.hook, first_3s=s.first_3s,
                     middle=s.middle + " Keep it unpolished — organic reach punishes "
                                       "anything that reads as an ad.",
                     cta=_ORGANIC_CTAS[i % len(_ORGANIC_CTAS)], emotion=s.emotion)


def build_pack(
    product: models.Product,
    psych: PsychProfile,
    llm: Optional[LLMClient] = None,
    n_hooks: int = 50,
    n_concepts: int = 50,
    n_scripts: int = 20,
) -> CreativePack:
    llm = llm or LLMClient()
    hooks = generate_hooks(product.name, psych, n=n_hooks, llm=llm,
                           category=product.category)
    paid = generate_scripts(product.name, psych, hooks, n=n_scripts, llm=llm)
    organic = [_soften_for_organic(s, i) for i, s in enumerate(paid[:n_scripts])]
    concepts = ugc_concepts(product, psych, n=n_concepts)
    from .realism import prompts_for_scripts
    pack = CreativePack(
        product=product, psych=psych, hooks=hooks, concepts=concepts,
        paid_scripts=paid, organic_scripts=organic, ctas=cta_variations(20),
        caption_list=captions(product, psych, 20), tag_list=hashtags(product),
        voiceover=voiceover_lines(product, psych), broll=broll_ideas(product),
        thumbnails=thumbnail_ideas(product),
        realism_prompts=prompts_for_scripts(product, paid, n=5),
    )
    # Compliance sweep over every piece of copy that could ship.
    texts = ([h.text for h in hooks] + [c.text for c in concepts]
             + [s.first_3s for s in paid] + [s.middle for s in paid]
             + [s.cta for s in paid] + pack.ctas + pack.caption_list + pack.voiceover)
    pack.compliance = [review_text(t) for t in texts]
    return pack
