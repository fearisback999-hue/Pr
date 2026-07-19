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
    key = f"{product.id}:{scene[:40]}"
    setting_pool = tuple(SETTINGS)
    if persona and persona.settings:
        owned = tuple(s for s in persona.settings if s in SETTINGS)
        setting_pool = owned or setting_pool
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
    wardrobe = persona.outfit_for(product.id) if persona else ""

    layers = {
        "setting": setting_name,
        "camera": _pick(CAMERA_TALK, key, index + 13),
        "camera_demo": _pick(CAMERA_DEMO, key, index + 14),
        "lighting": s["lighting"],
        "environment": s["environment"],
        "audio": s["audio"],
        "behavior": _pick(s["behaviors"], key, index + 15),
        "skin": _pick(SKIN, key, index + 16),
        "motion": _pick(MOTION, key, index + 17),
        "speech": _pick(tuple(persona.speech_quirks), key, index + 18)
                  if persona and persona.speech_quirks
                  else _pick(SPEECH, key, index + 18),
        "interaction": _pick(INTERACTION, key, index + 19),
        "lens": f"{t1}; {t2}",
        "casting": casting,
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
