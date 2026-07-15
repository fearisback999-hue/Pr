"""Naturalism layer for Higgsfield prompts: make AI-generated UGC-style ads feel like
a real phone video — natural light, handheld imperfection, human micro-behavior —
instead of plastic, cinematic, obviously-synthetic output.

The line this module holds (and won't help cross): naturalism is CRAFT — labeled AI
content that feels native performs; over-polished content reads as an ad and dies.
Deception is not the goal: TikTok requires disclosure of substantially AI-generated
commerce content, the FTC treats AI content passed off as a real person's genuine
experience as deceptive advertising, and this engine's export path already refuses
assets missing the AIGC disclosure. Every prompt this module emits carries that
reminder. Make it feel human; label it honestly. Those are compatible — that's the
whole point.

No fake "realism score 0–100" here: nothing in this codebase pretends to measure what
it can't. Instead: a deterministic prompt composer over researched naturalism layers,
plus the human QA checklist to run on every generated asset before export.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ..db import models
from .compliance import DISCLOSURE
from .scripts import UGCScript

# ── the naturalism layers (curated, not exhaustive — one pick per layer per prompt) ──
CAMERA = (
    "handheld iPhone framing with tiny natural shakes and one small reframe mid-shot",
    "casual phone camera hold, slight tilt, brief autofocus breathing when the product moves",
    "front-camera selfie distance, arm-length wobble, imperfect headroom",
    "propped-phone static shot that gets picked up mid-clip, natural stabilization wobble",
    "walking handheld, gentle bounce, micro exposure shifts as the light changes",
)
LIGHTING = (
    "morning bedroom sunlight through blinds, uneven across the frame",
    "warm kitchen ceiling light, slight color cast, everyday dimness",
    "cloudy daylight from a window to one side, soft and unglamorous",
    "golden hour through a car window, moving shadows",
    "ordinary office fluorescent, a bit flat and green-ish",
    "store aisle lighting, mixed color temperature",
)
SKIN_AND_FACE = (
    "natural skin texture with visible pores and slight unevenness, no beauty-filter smoothing",
    "real complexion: small blemish, fine facial hair, natural lip texture, tiny eye reflections",
    "unretouched face, subtle under-eye shadows, asymmetric smile",
)
MOTION = (
    "movement with real weight and momentum: natural pauses, blinking, breathing, small posture corrections",
    "casual product handling — fingers adjust grip, a slight fumble, then a natural recovery",
    "head and eye movement that wanders briefly before returning to the product",
)
BEHAVIOR = (
    "glances at phone once, then back",
    "adjusts shirt and fixes hair briefly mid-sentence",
    "takes a sip of coffee, sets the mug down out of frame",
    "laughs slightly at their own reaction, small thinking pause",
    "scratches cheek, looks away for a beat while talking",
)
ENVIRONMENT = (
    "lived-in bedroom: laundry on a chair, charger cable on the nightstand, slightly rumpled bed",
    "real kitchen counter clutter: mug, keys, a plant, yesterday's mail",
    "messy desk with notebook, water bottle, tangled earbuds",
    "car interior with a bag on the passenger seat, seatbelt visible",
    "hallway by the front door: shoes, a backpack, coats on hooks",
)
AUDIO = (
    "room echo with faint air-conditioner hum, natural breathing between phrases",
    "outdoor ambience: distant traffic, a bird, clothing rustle on the mic",
    "kitchen background: fridge hum, a clink, ordinary phone-mic compression",
    "car interior road noise, turn-signal click, slightly boomy phone audio",
)
LENS = (
    "smartphone HDR look, slight motion blur on fast moves, tiny sensor noise in shadows",
    "auto white balance drifting slightly mid-clip, minor digital sharpening, compressed social-video texture",
    "brief focus hunt when the product comes close to the lens, mild lens flare from the window",
)
PRODUCT_INTERACTION = (
    "product handled like an owned object: opened imperfectly, rotated casually, set down off-center",
    "product picked up from real clutter, fingerprints plausible, never floating or perfectly centered",
    "product shown mid-use with natural grip changes and one small handling mistake",
)

NEGATIVE = (
    "studio lighting, rim light, beauty lighting, cinematic grade, plastic airbrushed skin, "
    "symmetrical frozen face, robotic motion, perfect posture, floating product, centered "
    "hero shot, impossible shadows, CGI texture, influencer over-energy, over-editing"
)

# Human QA before export — generation artifacts a prompt can't fully prevent.
ARTIFACT_CHECKLIST = (
    "hands: five fingers, natural joints, no merging with the product",
    "eyes: blinking present, gaze shifts, no dead-eye stare or metronome blinks",
    "product: consistent shape/logo across frames, contact shadows where it touches surfaces",
    "skin: texture survives motion (no wax under movement)",
    "physics: hair/clothing move with the body; nothing floats or clips",
    "background: text/objects stay stable frame-to-frame (no morphing clutter)",
    "audio: lip-sync drift, breaths present, no uncanny silence between words",
    "the AIGC disclosure label is ON — non-negotiable; export refuses without it",
)


@dataclass
class RealismPrompt:
    scene: str                       # what happens (from the script beat)
    prompt: str                      # the composed Higgsfield-ready prompt
    negative: str = NEGATIVE
    disclosure_note: str = DISCLOSURE
    layers: dict = field(default_factory=dict)

    def render(self) -> str:
        return (
            f"PROMPT: {self.prompt}\n"
            f"NEGATIVE: {self.negative}\n"
            f"NOTE: label as AI-generated on upload — {self.disclosure_note.split('.')[0]}."
        )


def _pick(options: tuple, key: str, salt: int) -> str:
    """Deterministic variety: same product+index always composes the same prompt."""
    h = int(hashlib.sha256(f"{key}:{salt}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def enhance_prompt(
    product: models.Product,
    scene: str,
    index: int = 0,
    setting: str = "",
) -> RealismPrompt:
    """Compose a naturalism-enhanced Higgsfield prompt for one scene/beat.

    `scene` is what happens (e.g. a script's demo beat); this wraps it in the phone-real
    layers: camera, light, skin, motion, behavior, environment, audio, lens, handling.
    """
    key = f"{product.id}:{scene[:40]}"
    layers = {
        "camera": _pick(CAMERA, key, index),
        "lighting": _pick(LIGHTING, key, index + 1),
        "skin": _pick(SKIN_AND_FACE, key, index + 2),
        "motion": _pick(MOTION, key, index + 3),
        "behavior": _pick(BEHAVIOR, key, index + 4),
        "environment": setting or _pick(ENVIRONMENT, key, index + 5),
        "audio": _pick(AUDIO, key, index + 6),
        "lens": _pick(LENS, key, index + 7),
        "interaction": _pick(PRODUCT_INTERACTION, key, index + 8),
    }
    prompt = (
        f"Vertical 9:16 phone video, UGC style, NOT cinematic. {scene} "
        f"Camera: {layers['camera']}. Lighting: {layers['lighting']}. "
        f"Person: {layers['skin']}; {layers['motion']}; incidental behavior: "
        f"{layers['behavior']}. Setting: {layers['environment']}. "
        f"Product: {layers['interaction']}. Audio feel: {layers['audio']}. "
        f"Image character: {layers['lens']}. Pacing: natural pauses, real speech "
        f"rhythm, no influencer over-energy, minimal editing."
    )
    return RealismPrompt(scene=scene, prompt=prompt, layers=layers)


def prompts_for_scripts(
    product: models.Product, scripts: list[UGCScript], n: int = 5,
) -> list[RealismPrompt]:
    """Naturalism-enhanced prompts for the first n scripts' demo beats."""
    out = []
    for i, s in enumerate(scripts[:n]):
        scene = (f"A regular person on camera: {s.first_3s} Then they demonstrate: "
                 f"{s.middle} They end naturally: {s.cta}")
        out.append(enhance_prompt(product, scene, index=i))
    return out


def render_qa_checklist() -> str:
    lines = ["## Pre-export QA — run on EVERY generated asset", ""]
    lines += [f"- [ ] {item}" for item in ARTIFACT_CHECKLIST]
    lines += ["", "Fail any box → regenerate or discard. The disclosure box is not a "
              "quality item — it's policy, and `export-creatives` enforces it."]
    return "\n".join(lines)
