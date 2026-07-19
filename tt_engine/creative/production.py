"""Production runbook: the exact step-by-step to turn a creative pack into finished
AI-UGC video, following the practitioner Seedance 2.0 pipeline.

Source: Eric (@ericdoesecom) Instagram reel, captured 2026-07-19 — an end-to-end
keyframe-first workflow. It converges with the independent research in
docs/research/AI_VIDEO_REALISM.md (keyframe-first is the #1 consistency lever) and
adds two concrete steps the engine wasn't generating: the base ACTOR image and the
ElevenLabs video-to-voice lip-sync voice pipeline.

The pipeline, per ad:
  1. ACTOR IMAGE — one still portrait of the AI creator (GPT Image / equivalent),
     reused as the reference for every scene. iPhone-15-Pro framing, flaws on
     person AND scene, no "photorealism".
  2. SCENE FIRST-FRAMES — for each script beat, a description → a first-frame image
     of the actor-in-scene (+ product photo when the beat shows it).
  3. ANIMATE — Seedance generates each scene from its starting frame; dialogue goes
     in the prompt; the frame holds the character.
  4. VOICE — ONE consistent voice: ElevenLabs video-to-voice lip-syncs it onto the
     on-camera clips; text-to-voice (same voice) covers narration-only lines.
  5. ASSEMBLE — CapCut: cut together, auto-captions, real B-roll for extra realism.

This module PLANS and documents — it never generates or spends. Generation stays the
approval-gated `creative --confirm` / autopilot `generate` step, and the AIGC
disclosure label is non-negotiable at export.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..db import models
from .compliance import DISCLOSURE
from .concepts import CreativePack
from .persona import Persona, load_persona, validate_persona
from .realism import (
    SETTINGS,
    ImagePrompt,
    _pick,
    actor_image_prompt,
    scene_frame_prompt,
    scene_video_prompt,
)
from .scripts import UGCScript


def _spoken(beat: str) -> str:
    """The words the actor actually SAYS — strip parenthetical stage directions
    ('(creator holds up the product)') so the lip-synced line is clean."""
    return re.sub(r"\s*\([^)]*\)", "", beat).strip()


def _ad_setting(product: models.Product, persona: Optional[Persona], ad_index: int) -> str:
    """One room per ad — a real UGC clip is one location. Chosen from the persona's
    owned rooms, deterministic per (product, ad)."""
    pool = tuple(SETTINGS)
    if persona and persona.settings:
        owned = tuple(s for s in persona.settings if s in SETTINGS)
        pool = owned or pool
    return _pick(pool, f"{product.id}:ad{ad_index}", 0)


@dataclass
class Scene:
    label: str                 # "hook (0–3s)" | "demo" | "CTA (final)"
    on_camera: bool            # actor speaking to camera (video-to-voice) vs narration
    dialogue: str              # the spoken line (empty for pure demonstration)
    shows_product: bool
    frame: ImagePrompt         # first-frame image prompt
    video: str                 # Seedance animate-the-frame prompt


@dataclass
class AdBuild:
    index: int
    emotion: str
    scenes: list[Scene]


@dataclass
class ProductionRunbook:
    product_id: str
    product_name: str
    persona_name: str
    actor: ImagePrompt
    voice_reference: str
    voice_description: str
    ads: list[AdBuild]
    warnings: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# Production runbook — {self.product_name} ({self.product_id})",
            "",
            f"> {DISCLOSURE}",
            "",
            "Keyframe-first Seedance pipeline (persona: "
            f"**{self.persona_name}**). Generate the actor once, then per scene: "
            "first-frame image → animate → one consistent voice → assemble. "
            "This runbook plans; it never spends — generation is the confirmed "
            "`creative`/autopilot `generate` step.",
            "",
        ]
        if self.warnings:
            lines += ["## ⚠ Before you start", ""]
            lines += [f"- {w}" for w in self.warnings] + [""]

        lines += [
            "## Step 1 — Generate the actor (ONCE)", "",
            "Make one still portrait of the persona in your image tool (GPT Image / "
            "equivalent). Save the output; it's the reference attached to every scene "
            "below, and the seed for the 20–25-photo Soul-ID training set.", "",
            "```", self.actor.render(), "```", "",
            "## Step 2–4 — Per ad: first-frames → animate → dialogue", "",
        ]
        for ad in self.ads:
            lines += [f"### Ad {ad.index} — targets {ad.emotion}", ""]
            for sc in ad.scenes:
                mode = ("on-camera (lip-synced)" if sc.on_camera else "narration only")
                tags = [mode]
                if sc.shows_product:
                    tags.append("product in frame")
                lines += [f"**{sc.label}** · _{', '.join(tags)}_", ""]
                if sc.dialogue:
                    lines += [f"- Line: “{sc.dialogue}”", ""]
                lines += ["- First-frame image:", "```", sc.frame.render(), "```",
                          "- Animate (Seedance, from that frame):", "```", sc.video,
                          "```", ""]

        lines += [
            "## Step 5 — Voice (ONE voice, pinned)", "",
            f"Persona voice: {self.voice_description or '(describe it in the creator bible)'}",
            f"Canonical reference clip: `{self.voice_reference or '(none set — pin a ≤15s clip)'}`",
            "",
            "- On-camera scenes: ElevenLabs **video-to-voice** to lip-sync THIS voice "
            "onto the generated clips — a single voice across every ad is the audio "
            "equivalent of the Soul ID.",
            "- Narration-only lines: ElevenLabs **text-to-voice** with the SAME voice "
            "so on-camera and voiceover are indistinguishable.",
            "",
            "## Step 6 — Assemble (CapCut)", "",
            "- Cut the scenes in order; keep it single-take-feeling, minimal editing.",
            "- Auto-generate captions (native TikTok-style).",
            "- Drop in a little REAL B-roll (hands, the product, the room) — the "
            "practitioner tip for extra realism, and it doubles as honest proof.",
            "",
            "## Before export — non-negotiable", "",
            "- Run the pre-export QA checklist ON A PHONE (`creative` pack prints it).",
            "- The AIGC disclosure label goes ON every upload — `export-creatives` "
            "refuses assets without it. Outcome proof stays REAL footage; the persona "
            "never fabricates a result.",
        ]
        return "\n".join(lines) + "\n"


def _scenes_for_script(
    product: models.Product, script: UGCScript, persona: Optional[Persona], ad_index: int
) -> list[Scene]:
    """Map a 3-beat script to three scenes: hook (talk), demo (show product),
    CTA (talk). Beat text drives the frame moment and the spoken line."""
    base = ad_index * 3
    setting = _ad_setting(product, persona, ad_index)   # ONE room for the whole ad
    beats = [
        ("hook (0–3s)", True, _spoken(script.first_3s), script.first_3s, False),
        ("demo", False, "", script.middle, True),
        ("CTA (final)", True, _spoken(script.cta), script.cta, False),
    ]
    scenes: list[Scene] = []
    for i, (label, on_cam, dialogue, moment, shows) in enumerate(beats):
        frame = scene_frame_prompt(product, moment, persona=persona, setting=setting,
                                   index=base + i, needs_product=shows)
        video = scene_video_prompt(product, moment, dialogue=dialogue,
                                   persona=persona, index=base + i)
        scenes.append(Scene(label=label, on_camera=on_cam, dialogue=dialogue,
                            shows_product=shows, frame=frame, video=video))
    return scenes


def build_runbook(
    product: models.Product,
    pack: CreativePack,
    persona: Optional[Persona] = None,
    n_ads: int = 3,
) -> ProductionRunbook:
    """Assemble the full production runbook from a creative pack. Uses the first
    n_ads paid scripts (the ones the pack already naturalism-enhanced)."""
    if persona is None:
        persona = load_persona()
    actor = actor_image_prompt(persona)
    ads = [
        AdBuild(index=i + 1, emotion=s.emotion,
                scenes=_scenes_for_script(product, s, persona, i))
        for i, s in enumerate(pack.paid_scripts[:n_ads])
    ]
    warnings = validate_persona(persona) if persona else validate_persona(None)
    return ProductionRunbook(
        product_id=product.id, product_name=product.name,
        persona_name=persona.name if persona else "generic actor",
        actor=actor,
        voice_reference=persona.voice_reference if persona else "",
        voice_description=persona.voice_description if persona else "",
        ads=ads, warnings=warnings,
    )
