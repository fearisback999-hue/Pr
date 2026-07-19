"""Slideshow carousels: the volume lever — TikTok photo-mode posts from still images.

Source: a practitioner transcript (captured 2026-07-19) running AI slideshow
carousels at agency scale: images are an order of magnitude cheaper and faster to
generate than video, so slideshow volume buys more shots at the algorithm per
dollar. His pro tip, encoded here: have the model COVER THE FACE WITH THE PHONE
(mirror-selfie style) — it reads more candid AND converts better. It's also
quietly perfect for AI content: the face is where AI tells live, so hiding it
removes the hardest thing to get right, while wardrobe, jewelry, and the room
still pin the persona's continuity.

Volume honesty (the number that needed a reality check): "550 slideshows/day" is
a MULTI-BRAND AGENCY number spread across many accounts. One shop posting like
that reads as spam to the platform and to people. The sane single-store cadence
this module plans for: 2–4 slideshows/day alongside the video posts — still 10×
the surface area of video-only, without torching the account.

Same non-negotiables as everywhere else: every post carries the AIGC label, and
outcome claims stay off the slides — a slideshow can SHOW the product; proof of
results stays real footage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..db import models
from ..psychology import PsychProfile
from .compliance import DISCLOSURE
from .hooks import generate_hooks
from .persona import Persona, load_persona
from .realism import IMAGE_NEGATIVE, SETTINGS, ImagePrompt, _pick

# Sane single-store cadence (heuristic, stated): slideshows are cheap, accounts
# are not. The agency-scale number in the source is across MANY brands.
POSTS_PER_DAY = 3
SLIDES_PER_POST = 5

# Slide photo styles. "mirror-selfie-face-covered" is the practitioner tip — and
# doubles as the lowest-AI-tell style we have, so it anchors every post.
STYLES = (
    "mirror selfie, phone covering the face — candid, fewer tells, converts",
    "POV: product held out in one hand toward the camera, room behind",
    "casual flat-lay on the bed/counter, everyday clutter at the edges",
    "over-the-shoulder look at the product in use, slightly too close",
    "close-up detail shot, texture visible, imperfect focus on the edge",
)


@dataclass
class Slide:
    role: str                 # hook | context | demo | detail | cta
    style: str
    image: ImagePrompt
    overlay: str              # the text ON the slide (TikTok text tool)


@dataclass
class SlideshowPost:
    index: int
    hook: str
    setting: str              # ONE room per post — same rule as video ads
    slides: list[Slide]
    caption: str

    def render(self) -> str:
        lines = [f"### Slideshow {self.index} — “{self.hook}”",
                 f"_One room: {self.setting} · {len(self.slides)} slides_", ""]
        for i, sl in enumerate(self.slides, 1):
            lines += [f"**Slide {i} ({sl.role})** — {sl.style}",
                      f"- Overlay text: “{sl.overlay}”" if sl.overlay else
                      "- Overlay text: (none — let the image breathe)",
                      "```", sl.image.render(), "```", ""]
        lines += [f"**Caption:** {self.caption}", ""]
        return "\n".join(lines)


@dataclass
class SlideshowPlan:
    product_id: str
    product_name: str
    persona_name: str
    posts: list[SlideshowPost]
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# Slideshow carousels — {self.product_name} ({self.product_id})",
            "",
            f"> {DISCLOSURE}",
            "",
            f"Persona: **{self.persona_name}**. Cadence: ~{POSTS_PER_DAY} slideshows/"
            f"day for one store (the '550/day' agency number is spread across many "
            "accounts — one shop posting like that reads as spam). Images cost ~10× "
            "less than video: this is the volume lever, video carries the story.",
            "",
        ]
        for p in self.posts:
            lines.append(p.render())
        lines += ["## Rules that don't move", ""]
        lines += [f"- {n}" for n in self.notes]
        return "\n".join(lines) + "\n"


_OVERLAYS = {
    "context": ("POV: you finally found it", "wait for the last slide",
                "I was today years old", "this took me way too long to find"),
    "detail": ("look at the {detail}", "the quality for the price is unreal",
               "zoom in", "this part sold me"),
    "cta": ("link in bio before it's gone", "tap the cart, thank me later",
            "save this for payday", "sharing before it sells out"),
}


def _slide_image(product: models.Product, persona: Optional[Persona],
                 style: str, setting: str, role: str, salt: int) -> ImagePrompt:
    s = SETTINGS[setting]
    face_covered = "phone covering the face" in style
    # Flat-lays and close-ups have no person in frame — describing an outfit there
    # is itself an incoherence tell. Only person-in-frame styles carry the persona.
    personless = "flat-lay" in style or "close-up" in style
    show_product = role in ("demo", "detail", "hook")

    if personless:
        identity = "no person in frame — the product and the room do the talking"
        wardrobe = ""
    else:
        who = (f"{persona.name}, the store's recurring persona" if persona
               else "an ordinary-looking person")
        identity = (f"{who} — face hidden by the phone, identity carried by the "
                    "outfit and the room" if face_covered else
                    f"{who}, matched from the actor reference image")
        wardrobe = persona.outfit_for(product.id) if persona else ""
    prompt = (
        f"Casual photo shot on an iPhone 15 Pro, vertical 9:16, NOT professional. "
        f"Style: {style}. {identity}. "
        + (f"Wearing {wardrobe}. " if wardrobe else "")
        + f"Setting: {s['environment']}. Lighting: {s['lighting']}. "
        + (f"The {product.name} is clearly visible and naturally placed. "
           if show_product else "")
        + "Real-world flaws on person and scene: imperfect framing, everyday "
        "clutter, phone-camera texture, nothing staged-looking."
    )
    attach = ("" if (face_covered or personless) else "actor reference image")
    if show_product:
        attach = (attach + " + " if attach else "") + f"{product.name} product photo"
    return ImagePrompt(kind="scene-frame", prompt=prompt,
                       negative=IMAGE_NEGATIVE, attach=attach or "(none)")


def build_slideshows(
    product: models.Product,
    psych: PsychProfile,
    n: int = POSTS_PER_DAY,
    persona: Optional[Persona] = None,
) -> SlideshowPlan:
    if persona is None:
        persona = load_persona()
    hooks = generate_hooks(product.name, psych, n=max(n, 4))
    short = product.name.split("(")[0].strip()

    posts: list[SlideshowPost] = []
    for i in range(n):
        hook = hooks[i % len(hooks)].text
        pool = tuple(SETTINGS)
        if persona and persona.settings:
            owned = tuple(s for s in persona.settings if s in SETTINGS)
            pool = owned or pool
        setting = _pick(pool, f"{product.id}:slideshow{i}", 0)

        # Slide arc: hook → context → demo → detail → CTA. The face-covered
        # mirror-selfie anchors slide 1 (the practitioner tip: it converts).
        roles = ("hook", "context", "demo", "detail", "cta")
        slides = []
        for j, role in enumerate(roles):
            style = STYLES[0] if role == "hook" else _pick(STYLES[1:],
                                                           f"{product.id}:{i}", j)
            overlay = {
                "hook": hook,
                "context": _pick(_OVERLAYS["context"], f"{product.id}:{i}", j + 10),
                "demo": f"the {short}, mid-use — no filter",
                "detail": _pick(_OVERLAYS["detail"], f"{product.id}:{i}", j + 20)
                          .format(detail="stitching" if "strap" in short.lower()
                                  else "details"),
                "cta": _pick(_OVERLAYS["cta"], f"{product.id}:{i}", j + 30),
            }[role]
            slides.append(Slide(role=role, style=style, overlay=overlay,
                                image=_slide_image(product, persona, style,
                                                   setting, role, j)))
        caption = (f"{hook} #{short.split()[0].lower()} — AI-generated content, "
                   "labeled as such.")
        posts.append(SlideshowPost(index=i + 1, hook=hook, setting=setting,
                                   slides=slides, caption=caption))

    notes = [
        "the AIGC label goes on EVERY slideshow — same rule as video, no exceptions",
        "no outcome claims on slides or overlays — show the product, not a promised "
        "result; proof stays real footage",
        f"cadence: ~{POSTS_PER_DAY}/day per store; the source's 550/day is an agency "
        "total across many brands — matching it on one account reads as spam",
        "one room per post, one outfit per product batch — continuity rules carry "
        "over from video",
        "face-covered slides need no actor reference; face-visible slides attach it",
    ]
    return SlideshowPlan(
        product_id=product.id, product_name=product.name,
        persona_name=persona.name if persona else "generic actor",
        posts=posts, notes=notes,
    )
