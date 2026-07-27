"""Naturalism layer v2 for Higgsfield prompts: make LABELED AI-generated UGC look as
real as a phone video can — coherent scenes, budgeted imperfections, human speech,
persona continuity.

The deal (operator's own words): maximum realism, label on. That's the correct trade —
TikTok requires disclosing substantially AI-generated commerce content and this
engine's export path refuses assets missing the disclosure; meanwhile nothing about
the label stops the content from *feeling* native. This module optimizes the feeling.

What v2 fixes over v1 (each was an AI tell):
  • INCOHERENCE — v1 sampled lighting/clutter/audio independently, so "golden-hour car
    window" could pair with "bedroom laundry". Real clips are one place, one time.
    v2 picks ONE setting; light, clutter, sound, and plausible behavior all derive
    from it.
  • IMPERFECTION OVERLOAD — stacking shake + flare + focus-hunt + WB drift + noise in
    one clip reads as a filter, not a phone. v2 budgets exactly TWO texture
    imperfections per clip and keeps the rest clean.
  • UNIFORM CAMERA — real people hold the phone differently to talk vs to demo. v2
    assigns camera by beat: selfie arm-length for the hook/CTA, propped or second-hand
    grip for the demo.
  • PERFECT SPEECH — flawless delivery is synthetic. v2 directs one small disfluency
    (a false start, a mid-sentence correction, a trailing "so… yeah") per clip.
  • CAST DRIFT — a different face per ad breaks the store-persona strategy. v2 carries
    the Soul ID / a consistent casting spec and a continuity block (same room, light,
    outfit across beats).

No fake 0–100 realism score — the honest instrument is the pre-export QA checklist,
run on a phone screen, where the ad will actually live.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

from ..config import CONFIG
from ..db import models
from .compliance import DISCLOSURE
from .persona import Persona, load_persona
from .scripts import UGCScript

# ── coherent settings: light + clutter + sound + plausible behavior as ONE bundle ──
SETTINGS: dict[str, dict[str, str | tuple[str, ...]]] = {
    "bedroom-morning": {
        "lighting": "morning sun through blinds, uneven stripes across the wall, no fill",
        "environment": "lived-in bedroom: laundry on a chair, charger on the nightstand, "
                       "slightly rumpled duvet",
        "audio": "quiet room tone, birds faint outside, duvet rustle on the mic",
        "behaviors": ("pushes hair back mid-sentence", "glances at the window once",
                      "shifts sitting position on the bed"),
    },
    "kitchen-evening": {
        "lighting": "warm ceiling light with a slight yellow cast, everyday dimness",
        "environment": "real kitchen counter: mug, keys, a plant, yesterday's mail pushed aside",
        "audio": "fridge hum, one distant clink, boomy phone-mic room echo",
        "behaviors": ("takes a sip from the mug and sets it down off-frame",
                      "leans a hip against the counter", "nudges the mail aside absently"),
    },
    "car-parked": {
        "lighting": "daylight through the windshield, moving cloud shadows, mild HDR flatness",
        "environment": "parked car interior, bag on the passenger seat, seatbelt hanging",
        "audio": "muffled street noise, a car passing, seat creak, close boomy voice",
        "behaviors": ("checks the rearview once out of habit", "rests an elbow on the wheel",
                      "adjusts the phone against the dash"),
    },
    "desk-office": {
        "lighting": "flat office fluorescent with a faint green cast, window daylight mixing in",
        "environment": "messy desk: notebook, water bottle, tangled earbuds, sticky notes",
        "audio": "keyboard clicks nearby, air-conditioner hum, chair squeak",
        "behaviors": ("glances at the monitor once", "clicks a pen twice without noticing",
                      "leans back and the chair creaks"),
    },
    "entryway": {
        "lighting": "hallway light plus daylight spilling from the next room, uneven",
        "environment": "front-door entryway: shoes in a pile, backpack against the wall, "
                       "coats on hooks",
        "audio": "hard-floor echo, keys jangling once, a door closing somewhere",
        "behaviors": ("toes off a shoe mid-clip", "hangs keys on the hook without looking",
                      "steps closer to the camera to make a point"),
    },
    "outside-walk": {
        "lighting": "overcast daylight, soft and unglamorous, no golden-hour glow",
        "environment": "ordinary sidewalk, parked cars, a hedge, nothing scenic",
        "audio": "traffic wash, wind buffeting the mic once, footsteps",
        "behaviors": ("steps aside for someone off-screen", "switches the phone to the "
                      "other hand", "looks both ways crossing a driveway"),
    },
}

# Camera by beat — people hold phones differently to talk vs to show.
CAMERA_TALK = (
    "front camera at arm's length, slight up-angle, imperfect headroom, elbow wobble",
    "front camera resting against something, person leans in and out of frame a little",
)
CAMERA_DEMO = (
    "rear camera in one hand while the other demonstrates, framing drifts and corrects",
    "phone propped against an object for the demo, person's hands enter from the side, "
    "slight tilt to the frame",
    "over-the-shoulder POV of the hands using the product, close and a bit too tight",
)

# Texture imperfections — EXACTLY TWO per clip (more reads as a filter).
TEXTURES = (
    "brief autofocus hunt when the product comes close to the lens",
    "one micro exposure shift as the framing moves past the light source",
    "slight motion blur on the fastest hand movement",
    "auto white balance drifting warmer for a moment mid-clip",
    "tiny sensor noise visible in the darkest corner of the frame",
    "one small accidental reframe that gets corrected",
)

SPEECH = (
    "starts a sentence, abandons it, restarts simpler — like talking to a friend",
    "one 'um' and a mid-sentence self-correction, otherwise fluent",
    "trails off with 'so… yeah' before the last beat",
    "talks slightly too fast at the start, settles down after the first line",
)

SKIN = (
    "natural skin texture with visible pores and slight unevenness, no beauty-filter "
    "smoothing, real lip texture, tiny catchlights in the eyes",
    "unretouched face: small blemish, fine facial hair, subtle under-eye shadows, "
    "asymmetric smile",
)
MOTION = (
    "movement with weight and momentum: natural pauses, blinking at irregular intervals, "
    "visible breathing, small posture corrections",
    "hands re-grip and fidget slightly; head turns lead the eyes by a beat",
)
INTERACTION = (
    "product handled like an owned object: opened imperfectly, rotated casually, set "
    "down off-center with a real contact sound",
    "product picked up from the clutter, grip adjusts once, never floating, never "
    "centered like a hero shot",
)

CASTING = (
    "ordinary-looking person in their 20s–30s, everyday clothes, not model-attractive, "
    "hair slightly imperfect",
    "regular person you'd pass on the street, comfortable on camera but not polished, "
    "wearing what they actually wore today",
)

NEGATIVE = (
    "studio lighting, rim light, beauty lighting, cinematic color grade, plastic "
    "airbrushed skin, perfect white teeth, symmetrical frozen face, robotic motion, "
    "metronome blinking, perfect posture, floating product, centered hero shot, "
    "impossible shadows, warped or morphing text and logos, extra fingers, jewelry "
    "that changes between frames, CGI texture, influencer over-energy, over-editing, "
    "stacked filter look"
)

# Pre-export QA — run on EVERY generated asset, on a phone screen.
ARTIFACT_CHECKLIST = (
    "watch it ON A PHONE at feed size — that's where tells show or vanish",
    "hands: five fingers, natural joints, no merging with the product",
    "eyes: blinking present and irregular, gaze shifts, no dead-eye stare",
    "product: consistent shape/label text across frames, contact shadows where it "
    "touches surfaces",
    "skin: texture survives motion (no wax under movement)",
    "physics: hair/clothing move with the body; nothing floats or clips",
    "background: clutter and any text stay stable frame-to-frame (no morphing)",
    "audio: lip-sync holds, breaths present, room tone continuous across cuts",
    "speech: the disfluency sounds accidental, not performed",
    "continuity: same room, light, and outfit across all beats",
    "the AIGC disclosure label is ON — non-negotiable; export refuses without it",
)

# The honest number (researched 2026-07): real operators report ~2 usable clips out
# of 7 for AI video with visible hand interaction — roughly a 30% keep rate. Faces
# drift by frame ~4; physics is "locally plausible, globally inconsistent". Plan to
# GENERATE 3–4× what you need and discard the tells — that discipline, not one lucky
# render, is what makes a feed look real.
USABLE_CLIP_RATE = 0.30
GENERATIONS_PER_USABLE = 4     # generate this many, expect ~1 keeper


def render_authenticity_guide() -> str:
    """The practical 'make it look real' guide — honest craft, honest odds, the QA
    gate. Consolidates what the naturalism layer bakes into prompts so an operator
    knows what they're aiming for and what to throw away."""
    keep_pct = int(USABLE_CLIP_RATE * 100)
    lines = [
        "# Making AI video look as authentic as possible",
        "",
        "## The honest odds (so you're not surprised)",
        f"- Expect to KEEP roughly {keep_pct}% of what you generate — real operators "
        f"report ~2 usable clips in 7 when hands are involved. Generate "
        f"~{GENERATIONS_PER_USABLE}× what you need and DISCARD the tells. That "
        "discipline is the whole trick; there is no one-render magic.",
        "- Nobody can promise 'identical to a real person'. Some clips pass, many "
        "don't. The label is on regardless — the goal is native-feeling, not deception.",
        "",
        "## What the engine already bakes into every prompt",
        "- Shot 'on an iPhone', single-take, NOT cinematic; the word 'photorealism' is "
        "banned (it pushes the plastic look).",
        "- ONE coherent setting (light + clutter + sound match); exactly TWO texture "
        "imperfections, not nine (over-imperfection reads as a filter).",
        "- Real skin (pores, a blemish), irregular blinking, natural motion, one speech "
        "disfluency; the persona's face/wardrobe/room pinned for continuity.",
        "- Keyframe-first: generate a still, approve it, THEN animate — the single "
        "biggest anti-drift lever.",
        "",
        "## The tells to hunt (discard on ANY of these)",
    ]
    lines += [f"- {item}" for item in ARTIFACT_CHECKLIST]
    lines += [
        "",
        "## Craft tips that move the needle",
        "- Watch every candidate ON A PHONE at feed size — tells hide on a big screen.",
        "- Favour shots that hide the hardest failures: hands out of frame or still, "
        "face-covered mirror selfies (a proven format AND fewer face tells), short 8s "
        "clips (less time to drift).",
        "- **The fallback ladder (`shot-mode`):** if faces keep failing, drop a tier — "
        "`face_light` (face hidden) then `faceless` (chest-down / hands / POV, "
        "voiceover instead of lip-sync). Faceless deletes the two hardest classes "
        "entirely and is often MORE realistic. e.g. shorts → a chest-down try-on.",
        "- Pin ONE voice (ElevenLabs video-to-voice / a reference clip) across every "
        "clip — a shifting voice is as obvious as a shifting face.",
        "- Outcome proof stays REAL footage — a generated 'result' is fabricated "
        "evidence, and the label doesn't cover that.",
        "",
        "`authenticity` prints this; `production <id>` and `slideshows <id>` apply it.",
    ]
    return "\n".join(lines) + "\n"


@dataclass
class RealismPrompt:
    scene: str
    prompt: str
    negative: str = NEGATIVE
    disclosure_note: str = DISCLOSURE
    layers: dict = field(default_factory=dict)

    def render(self) -> str:
        return (
            f"PROMPT: {self.prompt}\n"
            f"NEGATIVE: {self.negative}\n"
            f"NOTE: label as AI-generated on upload — {self.disclosure_note.split('.')[0]}."
        )


def _pick(options, key: str, salt: int):
    h = int(hashlib.sha256(f"{key}:{salt}".encode()).hexdigest(), 16)
    return options[h % len(options)]


# ── image prompts: the keyframe-first workflow ──────────────────────────────────
# The practitioner pipeline (Eric @ericdoesecom, Seedance 2.0 workflow, captured
# 2026-07-19): generate a still ACTOR image once, then a per-scene FIRST-FRAME image
# (the same actor dropped into the scene, product attached), then ANIMATE each frame.
# Starting frames are the #1 character-consistency lever — the video model is
# constrained by the image instead of re-inventing the person. His three image rules,
# encoded here: shoot "on an iPhone 15 Pro", add flaws to BOTH the character and the
# scenery, and never use the word "photorealism" (it pushes the model toward the
# plastic stock-photo look — the opposite of what UGC needs).
IMAGE_NEGATIVE = (
    "photorealism, hyperrealistic, 8k, ultra-detailed, magazine retouching, "
    "airbrushed skin, perfect symmetry, studio lighting, stock-photo look, beauty "
    "filter, plastic skin, flawless complexion, CGI render, over-sharpened, "
    "professional headshot"
)

# ── shot modes: the fallback ladder for when AI struggles ───────────────────────
# The face is the #1 AI failure class and lip-sync the #2. If your generations look
# off, you don't fight them — you shoot AROUND them. Each tier down removes a hard
# failure class; the bottom tier is often MORE realistic, not less (a faceless
# chest-down try-on has nothing to drift). Same product, same honesty, the AIGC
# label stays on — you're just choosing framing you can reliably land.
SHOT_MODES = ("full", "face_light", "faceless")

_SHOT_MODE_SPEC = {
    "full": {
        "label": "Full — face + talking to camera (most sophisticated, hardest for AI)",
        "face": True, "talks": True,
        "framing": "",                       # category camera decides
        "identity": "",                      # persona casting as normal
        "voice": "lip-synced on camera",
        "when": "use when your test generations already look clean",
    },
    "face_light": {
        "label": "Face-light — face hidden by the phone / turned away",
        "face": False, "talks": True,
        "framing": "mirror-selfie or turned-away framing with the phone covering the "
                   "face; the face is NOT clearly visible",
        "identity": "identity carried by the outfit, hair, and room — face obscured, "
                    "so no face reference needed",
        "voice": "voiceover — face hidden, so lip-sync doesn't have to be perfect",
        "when": "drop here first if faces come out uncanny but you still want a person",
    },
    "faceless": {
        "label": "Faceless — chest-down / hands / POV (most achievable)",
        "face": False, "talks": False,
        "framing": "CROP ABOVE THE CHIN — no face in frame at all: chest-down, "
                   "waist-down, hands-only, or POV over the shoulder",
        "identity": "no face and no talking head — the body, the product, and the "
                    "hands carry it; removes the two hardest AI classes (faces + "
                    "lip-sync) entirely",
        "voice": "text-to-voice narration only (no lip-sync needed — no face on screen)",
        "when": "drop here when faces/lip-sync keep failing — often MORE realistic",
    },
}


def shot_mode_spec(mode: str) -> dict:
    return _SHOT_MODE_SPEC.get(mode, _SHOT_MODE_SPEC["full"])


@dataclass
class ImagePrompt:
    kind: str                     # "actor" | "scene-frame"
    prompt: str
    negative: str = IMAGE_NEGATIVE
    attach: str = ""              # what to attach in the image tool (refs, product photo)

    def render(self) -> str:
        lines = [f"PROMPT: {self.prompt}", f"NEGATIVE: {self.negative}"]
        if self.attach:
            lines.append(f"ATTACH: {self.attach}")
        return "\n".join(lines)


def actor_image_prompt(
    persona: Optional[Persona] = None, index: int = 0, avatar_note: str = ""
) -> ImagePrompt:
    """Step 1 — the base AI-actor portrait, generated ONCE and reused as the
    reference for every scene frame (and as the seed for the Soul-ID training set).

    `avatar_note` lets a category tune how the actor reads — clothing wants a
    camera-confident, aspirational look that could pass as the first frame of a
    TikTok (the practitioner's bar), while staying the same labeled persona."""
    if persona is None:
        persona = load_persona()
    if persona:
        who = persona.master_description
        if persona.forbidden:
            who += " (never changes: " + "; ".join(persona.forbidden) + ")"
        wardrobe = persona.outfit_for("actor-base")
    else:
        who = _pick(CASTING, "actor", index)
        wardrobe = ""
    prompt = (
        "Vertical portrait selfie shot on an iPhone 15 Pro, front camera at arm's "
        "length with the slight wide-angle distortion a phone selfie lens gives, "
        f"casual and candid. {who}. "
        + (f"Wearing {wardrobe}. " if wardrobe else "")
        + (f"Read: {avatar_note}. " if avatar_note else "")
        + "Plain everyday room in the background, natural window light with uneven "
        "exposure. Add real-world flaws to BOTH the person and the scene: slight "
        "skin unevenness, a few stray hairs, faint sensor noise, minor background "
        "clutter, imperfect framing. Looks like a real phone selfie a normal person "
        "took today — not a professional shot."
    )
    return ImagePrompt(kind="actor", prompt=prompt,
                       attach="(none — this IS the base actor; save the output as "
                              "the reference for every scene)")


def garment_swap_prompt(
    product: models.Product,
    persona: Optional[Persona] = None,
    setting: str = "",
    index: int = 0,
    garment_angles: tuple[str, ...] = ("front",),
    shot_mode: str = "full",
) -> ImagePrompt:
    """Clothing fit-check core (practitioner method): synthesize the MODEL wearing the
    operator's ACTUAL garment. The model comes from the actor reference; the garment
    comes from uploaded product photo(s). Multiple angles (front/back of a tee) are
    attached so the swap can render both — the model is real-consistent, the clothing
    is the real product, not a hallucinated approximation.

    `shot_mode` is the fallback ladder: 'faceless' crops the face out (chest-down /
    waist-down try-on) — no face to drift, so it lands reliably when full-face fails.
    """
    if persona is None:
        persona = load_persona()
    pool = tuple(SETTINGS)
    if persona and persona.settings:
        owned = tuple(s for s in persona.settings if s in SETTINGS)
        pool = owned or pool
    # Clothing lives in the try-on rooms.
    biased = tuple(s for s in pool if s in ("bedroom-morning", "entryway"))
    pool = biased or pool
    key = f"{product.id}:garment"
    setting_name = setting if setting in SETTINGS else _pick(pool, key, index)
    s = SETTINGS[setting_name]
    who = persona.name if persona else "the same model"
    angles = ", ".join(garment_angles)
    spec = shot_mode_spec(shot_mode)

    common = (
        f"wearing the EXACT garment from the attached clothing photo(s) — match its "
        f"cut, colour, pattern, print, and every detail precisely; do not redesign it. "
        f"Angles provided: {angles}. In front of a mirror: {s['environment']}. "
        f"Lighting: {s['lighting']}. Natural fit with real fabric drape and honest "
        "wrinkles — not a smoothed mannequin. Add phone-camera texture and imperfect "
        "framing."
    )
    if spec["face"]:
        prompt = (
            "Full-body try-on frame, vertical 9:16, shot on an iPhone 15 Pro, could "
            f"be the first frame of a TikTok. The SAME model from the attached "
            f"reference ({who}) {common} Keep the model's face EXACTLY as the "
            "reference — same person, no drift."
        )
        attach = f"model reference image + clothing photo(s): {angles}"
    else:
        # Faceless / face-light: crop the face out — the garment on the body is the
        # whole shot, and there's no face to drift. Often reads MORE real.
        prompt = (
            "Try-on frame, vertical 9:16, shot on an iPhone 15 Pro. "
            f"FRAMING: {spec['framing']}. A person {common} "
            "No face in frame — the fit and fabric are the subject."
        )
        attach = f"clothing photo(s): {angles}"
    return ImagePrompt(kind="garment-swap", prompt=prompt, attach=attach)


def scene_frame_prompt(
    product: models.Product,
    scene_beat: str,
    persona: Optional[Persona] = None,
    setting: str = "",
    index: int = 0,
    needs_product: bool = True,
    shot_mode: str = "full",
) -> ImagePrompt:
    """Steps 2–3 — the first-frame image for one scene: the SAME actor (attached
    reference) dropped into one of her rooms, product attached when the beat needs it.
    A faceless `shot_mode` crops the face out (hands / POV / product focus)."""
    if persona is None:
        persona = load_persona()
    setting_pool = tuple(SETTINGS)
    if persona and persona.settings:
        owned = tuple(s for s in persona.settings if s in SETTINGS)
        setting_pool = owned or setting_pool
    key = f"{product.id}:{scene_beat[:40]}"
    setting_name = setting if setting in SETTINGS else _pick(setting_pool, key, index)
    s = SETTINGS[setting_name]
    who = persona.name if persona else "the same actor"
    wardrobe = persona.outfit_for(product.id) if persona else ""
    spec = shot_mode_spec(shot_mode)
    scene = (f"in this setting: {s['environment']}. Lighting: {s['lighting']}. "
             f"Moment: {scene_beat}. "
             + (f"The {product.name} is visible and held naturally, matched from the "
                "attached product photo. " if needs_product else ""))
    if spec["face"]:
        prompt = (
            "First video frame, vertical 9:16, shot on an iPhone 15 Pro (slight "
            "wide-angle phone-lens distortion). The SAME "
            f"actor from the attached reference image ({who}), "
            + (f"wearing {wardrobe}, " if wardrobe else "")
            + scene
            + "Add flaws to the actor and the scenery so nothing looks too perfect: "
            "imperfect framing, real phone-camera texture. Match the reference face "
            "EXACTLY — same person, no drift.")
        attach = "actor reference image" + (
            f" + {product.name} product photo" if needs_product else "")
    else:
        prompt = (
            "First video frame, vertical 9:16, shot on an iPhone 15 Pro. "
            f"FRAMING: {spec['framing']} — NO face in frame. " + scene
            + "Real phone-camera texture, imperfect framing; the hands, product, and "
            "setting carry the shot.")
        attach = (f"{product.name} product photo" if needs_product else "(none)")
    return ImagePrompt(kind="scene-frame", prompt=prompt, attach=attach,
                       negative=IMAGE_NEGATIVE)


def scene_video_prompt(
    product: models.Product,
    motion_beat: str,
    dialogue: str = "",
    persona: Optional[Persona] = None,
    index: int = 0,
    shot_mode: str = "full",
) -> str:
    """Step 4 — the Seedance prompt to ANIMATE a starting frame (frame-first). The
    frame already locks face/wardrobe/setting, so this stays focused on motion, the
    spoken line (dialogue goes IN the prompt), and phone texture — and orders the
    model to hold the frame's identity.

    In a faceless `shot_mode` there's no talking head on screen, so dialogue becomes
    voiceover (no on-camera lip-sync to fail) and the 'keep the face' clause drops."""
    if persona is None:
        persona = load_persona()
    from .category_styles import style_for
    style = style_for(product.category)
    spec = shot_mode_spec(shot_mode)
    key = f"{product.id}:{motion_beat[:40]}"
    behavior = _pick(MOTION, key, index)
    t1 = _pick(TEXTURES, key, index + 10)
    speech_pool = (tuple(persona.speech_quirks)
                   if persona and persona.speech_quirks else SPEECH)
    speech = _pick(speech_pool, key, index + 18)
    grammar = f" Demo grammar ({style.label}): {style.demo_grammar}."
    if spec["face"]:
        said = (f" The actor says, naturally: \"{dialogue.strip()}\" ({speech})."
                if dialogue.strip() else "")
        hold = ("Keep the face, wardrobe, and setting IDENTICAL to the starting "
                "frame — no drift, no morphing.")
        framing = ""
    else:
        # No face on screen → the line is voiceover, and there's no face to hold.
        said = (f" VOICEOVER (not on camera): \"{dialogue.strip()}\"."
                if dialogue.strip() else "")
        hold = ("Keep the wardrobe, product, and setting IDENTICAL to the starting "
                "frame; NO face enters the frame.")
        framing = f" FRAMING: {spec['framing']}."
    return (
        "Animate the attached starting frame. Vertical 9:16, iPhone feel, single "
        f"take, NOT cinematic.{framing} Motion: {motion_beat} {behavior}.{said}"
        f"{grammar} {hold} Texture: {t1}. Natural pacing, real breathing, minimal "
        "editing."
    )


def enhance_prompt(
    product: models.Product,
    scene: str,
    index: int = 0,
    setting: str = "",
    soul_id: Optional[str] = None,
    hook_beat: str = "",
    demo_beat: str = "",
    cta_beat: str = "",
    persona: Optional[Persona] = None,
) -> RealismPrompt:
    """Compose one coherent, phone-real Higgsfield prompt.

    Pass the three beats separately when you have them (timeline + per-beat camera);
    `scene` alone works for a single-beat clip. One setting drives light/clutter/sound/
    behavior together; exactly two texture imperfections; one speech disfluency; the
    Soul ID (or a consistent casting spec) keeps the store persona stable across ads.

    With a `persona` (the creator bible, docs/persona/CREATOR.md): her master
    description opens the casting block verbatim, the setting is restricted to the
    rooms she owns, the whole batch wears ONE itemized outfit, and her speech quirks
    replace the generic disfluency pool — the research-backed anti-drift set.
    """
    from .category_styles import style_for
    style = style_for(product.category)

    key = f"{product.id}:{scene[:40]}"
    setting_pool = tuple(SETTINGS)
    if persona and persona.settings:
        owned = tuple(s for s in persona.settings if s in SETTINGS)
        setting_pool = owned or setting_pool
    # Category bias: a try-on lives in the bedroom, a gadget demo at the desk. The
    # intersection with the persona's rooms wins; her rooms are still the boundary.
    if style.setting_bias:
        biased = tuple(s for s in setting_pool if s in style.setting_bias)
        setting_pool = biased or setting_pool
    setting_name = setting if setting in SETTINGS else _pick(setting_pool, key, index)
    s = SETTINGS[setting_name]

    # Exactly two distinct texture imperfections.
    t1 = _pick(TEXTURES, key, index + 10)
    t2 = _pick(tuple(t for t in TEXTURES if t != t1), key, index + 11)

    soul = soul_id if soul_id is not None else CONFIG.higgsfield_soul_id
    if persona:
        casting = persona.casting_spec(soul)
    else:
        casting = (f"the store's recurring persona (Soul ID {soul}), consistent with "
                   f"every other ad" if soul else _pick(CASTING, key, index + 12))
    # Apparel's special case: the product IS the outfit — pinning the persona's
    # sweater over the garment being sold would be nonsense.
    if style.wardrobe_rule == "product-is-outfit":
        wardrobe = (f"the {product.name} itself — the product IS the outfit, styled "
                    "casually with what she'd actually pair it with"
                    + (f"; jewelry: {persona.jewelry}" if persona and persona.jewelry
                       else ""))
    else:
        wardrobe = persona.outfit_for(product.id) if persona else ""

    layers = {
        "setting": setting_name,
        "camera": _pick(CAMERA_TALK, key, index + 13),
        "camera_demo": style.camera_demo or _pick(CAMERA_DEMO, key, index + 14),
        "lighting": s["lighting"],
        "environment": s["environment"],
        "audio": s["audio"],
        "behavior": _pick(s["behaviors"], key, index + 15),
        "skin": _pick(SKIN, key, index + 16),
        "motion": _pick(MOTION, key, index + 17),
        "speech": _pick(tuple(persona.speech_quirks), key, index + 18)
                  if persona and persona.speech_quirks
                  else _pick(SPEECH, key, index + 18),
        "interaction": style.interaction or _pick(INTERACTION, key, index + 19),
        "lens": f"{t1}; {t2}",
        "casting": casting,
        "category_demo": style.demo_grammar,
    }
    if wardrobe:
        layers["wardrobe"] = wardrobe

    if hook_beat or demo_beat or cta_beat:
        timeline = (
            f"TIMELINE — 0–3s (hook, camera: {layers['camera']}): {hook_beat or scene} · "
            f"3–18s (demo, camera: {layers['camera_demo']}): {demo_beat} · "
            f"final 3s (CTA, back to the talking camera): {cta_beat}"
        )
    else:
        timeline = f"SCENE (camera: {layers['camera']}): {scene}"

    wardrobe_block = (f"WARDROBE (exact, identical in every beat and every clip of "
                      f"this batch): {wardrobe}. " if wardrobe else "")
    prompt = (
        f"Vertical 9:16 iPhone video, single-take UGC feel, NOT cinematic. "
        f"CASTING: {casting}. "
        f"{wardrobe_block}"
        f"SETTING ({setting_name}): {layers['environment']}. "
        f"LIGHTING: {layers['lighting']}. "
        f"{timeline} "
        f"PERSON: {layers['skin']}; {layers['motion']}; incidental: {layers['behavior']}. "
        f"SPEECH: {layers['speech']}. "
        f"PRODUCT: {layers['interaction']}. "
        f"DEMO GRAMMAR ({style.label}): {style.demo_grammar}. "
        f"AUDIO: {layers['audio']}; natural breathing between phrases. "
        f"REALISM TEXTURE (exactly these two, keep everything else clean): {t1}; {t2}. "
        f"CONTINUITY: same room, same light, same outfit across all beats. "
        f"PACING: real speech rhythm, natural pauses, no influencer over-energy, "
        f"minimal editing."
    )
    return RealismPrompt(scene=scene, prompt=prompt, layers=layers)


def prompts_for_scripts(
    product: models.Product,
    scripts: list[UGCScript],
    n: int = 5,
    soul_id: Optional[str] = None,
    persona: Optional[Persona] = None,
) -> list[RealismPrompt]:
    """Beat-structured prompts for the first n scripts (hook/demo/CTA timeline).
    The creator bible auto-loads when present so every batch carries the persona."""
    if persona is None:
        persona = load_persona()
    out = []
    for i, s in enumerate(scripts[:n]):
        scene = (f"A regular person on camera: {s.first_3s} Then they demonstrate: "
                 f"{s.middle} They end naturally: {s.cta}")
        out.append(enhance_prompt(
            product, scene, index=i, soul_id=soul_id,
            hook_beat=s.first_3s, demo_beat=s.middle, cta_beat=s.cta,
            persona=persona,
        ))
    return out


def render_qa_checklist() -> str:
    lines = ["## Pre-export QA — run on EVERY generated asset", ""]
    lines += [f"- [ ] {item}" for item in ARTIFACT_CHECKLIST]
    lines += ["", "Fail any box → regenerate or discard. The disclosure box is not a "
              "quality item — it's policy, and `export-creatives` refuses assets "
              "missing it."]
    return "\n".join(lines)
