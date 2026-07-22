"""Clothing fit-check runbook: the apparel-specific production method.

Source: a practitioner clothing transcript (captured 2026-07-19) — 500+ units sold
of one SKU with AI try-on "fit check" videos. The method's distinct moves, encoded:

  1. DEDICATED ACCOUNT — the persona posts fit-checks from her OWN creator-style
     account, not the brand account. Try-ons work because they read organic; a brand
     handle kills that. The store reposts/boosts winners.
  2. AVATAR BAR — the model reads camera-confident and aspirational, like the first
     frame of a real TikTok (tasteful, still a labeled AI persona).
  3. GARMENT SWAP — generate the model, upload the ACTUAL clothing photo(s), and
     synthesize the model wearing that exact garment. Multiple angles (front/back of
     a tee) go in as references so the swap renders both. The clothing is the real
     product, not a hallucination.
  4. SHORT FIT-CHECK CLIPS — ~8s each, a tight walk-in → turn → detail → soft-CTA arc.

Economics honesty: the source quotes ~$55/mo for ~180s of generation ≈ 23 eight-second
clips, "break even on 2–3 sales." We DON'T parrot "2–3" — when the product has a real
landed cost on file we compute how many sales actually cover $55 at its TRUE margin;
without one we say so (the standard refusal). And the AIGC label rides on every clip;
sizing/fit honesty replaces any fabricated results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..db import models
from ..economics import Economics
from ..economics.optimizer import DEFAULT_PAYMENT_RATE, true_economics
from .category_styles import style_for
from .compliance import DISCLOSURE
from .persona import Persona, load_persona, validate_persona
from .realism import (
    ImagePrompt,
    actor_image_prompt,
    garment_swap_prompt,
    scene_video_prompt,
)

# Practitioner economics (sourced, re-verify — tools/prices move): a $55/mo creator
# plan ≈ 180s of generation; 8s clips ⇒ ~22–23 clips/month.
GEN_PLAN_COST = 55.0
GEN_PLAN_SECONDS = 180
CLIP_SECONDS = 8
CLIPS_PER_MONTH = GEN_PLAN_SECONDS // CLIP_SECONDS      # 22


@dataclass
class FitCheckClip:
    index: int
    hook: str
    beats: list[tuple[str, str]]        # (label, motion/dialogue) across the ~8s
    garment_frame: ImagePrompt
    video: str


@dataclass
class FitCheckRunbook:
    product_id: str
    product_name: str
    persona_name: str
    model: ImagePrompt
    garment_angles: tuple[str, ...]
    clips: list[FitCheckClip]
    dedicated_account: str
    breakeven_note: str
    warnings: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# Clothing fit-check runbook — {self.product_name} ({self.product_id})",
            "",
            f"> {DISCLOSURE}",
            "",
            "The apparel try-on method: dedicated creator account, an aspirational "
            "model, the garment SWAPPED from your real product photos, short ~8s "
            "fit-check clips. Plans only — generation stays the confirmed step, and "
            "sizing/fit honesty replaces any fabricated result.",
            "",
            "## Step 0 — Account", "",
            f"- {self.dedicated_account}",
            "",
            "## Step 1 — Generate the model (ONCE)", "",
            "Aspirational, camera-confident, could be the first frame of a TikTok — "
            "the bible's face pinned, labeled AI persona.", "",
            "```", self.model.render(), "```", "",
            "## Step 2 — Garment swap", "",
            f"Upload your clothing photo(s) — angles: {', '.join(self.garment_angles)} "
            "(add back/side if the clip must show them). The model is synthesized "
            "wearing your EXACT garment:", "",
        ]
        for clip in self.clips:
            lines += [f"### Clip {clip.index} — “{clip.hook}” (~{CLIP_SECONDS}s)", ""]
            lines += ["- Garment-swap first frame:", "```", clip.garment_frame.render(),
                      "```", ""]
            lines += ["- Fit-check beats:"] + [f"    · {lbl}: {mot}"
                                               for lbl, mot in clip.beats] + [""]
            lines += ["- Animate (from the frame):", "```", clip.video, "```", ""]
        lines += [
            "## Economics (sourced — re-verify)", "",
            f"- ~${GEN_PLAN_COST:.0f}/mo ≈ {GEN_PLAN_SECONDS}s of generation ≈ "
            f"~{CLIPS_PER_MONTH} clips at {CLIP_SECONDS}s each.",
            f"- {self.breakeven_note}",
            "",
            "## Non-negotiable", "",
            "- AIGC label on every clip (export refuses without it).",
            "- Fit/sizing honesty is the proof — never fabricate a body result or a "
            "review; the garment on the model IS the honest demo.",
        ]
        if self.warnings:
            lines += ["", "## ⚠ Persona gaps before you start", ""]
            lines += [f"- {w}" for w in self.warnings]
        return "\n".join(lines) + "\n"


def _breakeven_note(product: models.Product, economics: Optional[Economics]) -> str:
    if economics is None or not economics.landed_known:
        return ("add a real supplier cost (`add-supplier`) and the engine will "
                "compute exactly how many sales cover the $55 at YOUR margin — "
                "without landed cost, '2–3 sales' is a guess, not a number")
    te = true_economics(economics.sell_price, economics.supplier_cost,
                        economics.ship_cost, DEFAULT_PAYMENT_RATE, 0.0)
    if te.true_profit <= 0:
        return (f"at the true fee stack this product's margin is ${te.true_profit:.2f}/"
                "unit — it loses money per sale, so no number of clips earns the $55 "
                "back; fix the economics first")
    import math
    sales = math.ceil(GEN_PLAN_COST / te.true_profit)
    return (f"at YOUR true margin (${te.true_profit:.2f}/unit) it takes ~{sales} "
            f"sale(s) to cover the ${GEN_PLAN_COST:.0f}/mo generation — from "
            f"~{CLIPS_PER_MONTH} clips, that's the bar to clear")


def build_fit_check(
    product: models.Product,
    hooks: list,
    persona: Optional[Persona] = None,
    economics: Optional[Economics] = None,
    n_clips: int = 3,
    garment_angles: tuple[str, ...] = ("front", "back"),
) -> FitCheckRunbook:
    """Build the clothing fit-check runbook. `hooks` are Hook objects (the pack's
    apparel-native hooks lead them). Each clip is a ~8s walk-in → turn → detail →
    soft-CTA arc off one garment-swap frame."""
    if persona is None:
        persona = load_persona()
    style = style_for(product.category)
    model = actor_image_prompt(persona, avatar_note=style.avatar_note)

    short = product.name.split("(")[0].strip()
    clips: list[FitCheckClip] = []
    for i in range(n_clips):
        hook = hooks[i % len(hooks)].text if hooks else f"{short} fit check"
        beats = [
            ("0–2s (walk in)", f"walk into mirror frame, {short} on, glance up — the hook"),
            ("2–5s (turn)", "turn once so the fit and fabric move; show front, then back"),
            ("5–7s (detail)", "handheld close on the waist/hem/fabric — honest fit note"),
            ("7–8s (soft CTA)", "back to the mirror, a natural 'linked below' — no hard sell"),
        ]
        frame = garment_swap_prompt(product, persona=persona, index=i,
                                    garment_angles=garment_angles)
        video = scene_video_prompt(product, "a full-body try-on: walk in, turn once "
                                   "showing front and back, then a close fit detail",
                                   dialogue=hook, persona=persona, index=i)
        clips.append(FitCheckClip(index=i + 1, hook=hook, beats=beats,
                                  garment_frame=frame, video=video))

    warnings = validate_persona(persona) if persona else validate_persona(None)
    return FitCheckRunbook(
        product_id=product.id, product_name=product.name,
        persona_name=persona.name if persona else "generic model",
        model=model, garment_angles=garment_angles, clips=clips,
        dedicated_account=style.dedicated_account,
        breakeven_note=_breakeven_note(product, economics),
        warnings=warnings,
    )
