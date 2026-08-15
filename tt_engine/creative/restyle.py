"""Video restyle — use YOUR OWN footage as the base, change everything around it.

You film the pull-up bar yourself: your hands, your reps, the real product doing the
real thing. Then this restyles that footage — a different person, a different wall
colour, a different room — while the product and the motion stay exactly as filmed.

Why this beats generating from scratch, and it is not a small difference:

  • The product is REAL. It is your actual item at your actual angles, so nothing is
    hallucinated about the thing you are selling — which is both the honesty problem
    and the realism problem solved at once.
  • The physics are REAL. Weight, sag, hand placement, how a bar flexes under load —
    this is exactly what generated video gets wrong and what viewers read as fake.
  • One base shoot yields many videos. Same ten seconds of footage becomes a version
    for every actor on the roster, which is the demographic testing you already do
    with specs, but grounded in real motion.

TWO HARD RULES, both structural rather than advisory:

  1. THE BASE VIDEO MUST BE YOURS. Restyling someone else's ad is the competitor-ad
     cloning this project already refuses — it is their copyrighted footage, often
     their likeness, and swapping the actor does not change either. `create_restyle`
     will not accept a job without an explicit ownership attestation.

  2. THE PRODUCT IS NEVER A RESTYLE TARGET. Changing the actor or the wall is set
     dressing. Changing the product misrepresents what the buyer receives, which is
     an FTC problem, a refund problem, and a shop-closing problem in that order.
     The product appears in PRESERVED, never in CHANGEABLE, and asking to change it
     is refused rather than quietly ignored.

Disclosure is mandatory and, if anything, more clearly required here than for a fully
generated clip: TikTok's rule names "substantially AI-altered" content — a changed
background or an altered appearance — which is precisely what this does.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..db import Database, models

# What a restyle may change: set dressing and the person, never the merchandise.
CHANGEABLE: dict[str, str] = {
    "actor":     "who is on camera — swap in a roster persona",
    "wall":      "wall colour and finish behind the subject",
    "room":      "the whole setting (bedroom → garage → gym corner)",
    "wardrobe":  "what the person is wearing",
    "lighting":  "time of day and light quality",
    "mood":      "overall colour grade and energy",
}

# What must survive untouched for the video to still be honest about the product.
PRESERVED: tuple[str, ...] = (
    "the product itself — shape, colour, finish, branding, size relative to the body",
    "the motion and physics — reps, sag, flex, hand placement, how it bears weight",
    "the timing and cut points of the original take",
    "anything that constitutes a claim about what the product does",
)

# Accepted container formats. Not a security boundary — a sanity check so a mistyped
# path fails here with a clear message instead of failing later at the vendor.
VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm")
MAX_BASE_MB = 200.0


class NotYourFootage(PermissionError):
    """Raised when a restyle is attempted without attesting ownership of the base."""


class ProductIsNotRestylable(ValueError):
    """Raised when the product itself is requested as a restyle target."""


@dataclass
class RestyleJob:
    id: Optional[int]
    product_id: str
    base_video: str
    changes: dict[str, str]          # target -> instruction
    actor_slug: str = ""
    notes: str = ""
    status: str = "draft"

    @property
    def base_name(self) -> str:
        return Path(self.base_video).name

    def render(self) -> str:
        lines = [
            f"# Restyle job{f' #{self.id}' if self.id else ''} — {self.product_id}"
            f"  [{self.status}]",
            "",
            f"BASE (yours, unaltered in substance): {self.base_name}",
            "",
            "## What changes",
        ]
        for target, instruction in self.changes.items():
            lines.append(f"  {target:9s} → {instruction}")
        if self.actor_slug:
            lines.append(f"  actor     → roster persona '{self.actor_slug}'")
        lines += ["", "## What is preserved exactly"]
        lines += [f"  • {p}" for p in PRESERVED]
        lines += [
            "",
            "## Assembled prompt",
            "```",
            build_prompt(self),
            "```",
            "",
            "Review the prompt above, then `restyle approve <id>` and "
            "`restyle generate <id> --confirm`. Generation is the step that spends.",
        ]
        return "\n".join(lines)


def _check_base(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(
            f"base video not found: {p}. Point at the file you actually filmed — the "
            "engine does not fetch video from anywhere.")
    if p.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError(f"'{p.suffix}' is not a video container the vendors accept "
                         f"({', '.join(VIDEO_SUFFIXES)})")
    size_mb = p.stat().st_size / 1e6
    if size_mb > MAX_BASE_MB:
        raise ValueError(f"base video is {size_mb:.0f}MB, over the {MAX_BASE_MB:.0f}MB "
                         "limit. Trim it to the 5–15 seconds you actually want "
                         "restyled — a shorter base also costs less to process.")
    if size_mb == 0:
        raise ValueError(f"{p.name} is empty (0 bytes)")
    return p


def validate_changes(changes: dict[str, str]) -> dict[str, str]:
    """Every requested change must be a known, permitted target."""
    clean: dict[str, str] = {}
    for target, instruction in changes.items():
        key = target.strip().lower()
        if key in ("product", "item", "merchandise", "packaging", "label"):
            raise ProductIsNotRestylable(
                f"'{target}' cannot be restyled. Changing the product changes what the "
                "buyer thinks they are getting — that is misrepresentation, not set "
                "dressing. Restyle the person and the room; film the product honestly.")
        if key not in CHANGEABLE:
            raise ValueError(
                f"unknown restyle target '{target}'. Choose from: "
                + ", ".join(f"{k} ({v})" for k, v in CHANGEABLE.items()))
        if not instruction.strip():
            raise ValueError(f"'{target}' has no instruction — say what it should become")
        clean[key] = instruction.strip()
    if not clean:
        raise ValueError("nothing to change — a restyle with no changes is just your "
                         "original video, which you already have")
    return clean


def build_prompt(job: RestyleJob) -> str:
    """The text a video-to-video model receives. The PRESERVE clause comes first and
    is stated in the strongest terms available, because everything downstream of a
    drifted product is a refund."""
    from .persona import persona_by_slug

    parts = [
        "VIDEO-TO-VIDEO RESTYLE of the supplied base clip.",
        "",
        "PRESERVE EXACTLY — do not reinterpret, redesign, or 'improve' any of these:",
    ]
    parts += [f"  - {p}" for p in PRESERVED]
    parts += [
        "  - the product must be pixel-faithful to the base clip; if the product "
        "cannot be preserved, fail rather than approximate it.",
        "",
        "CHANGE:",
    ]
    for target, instruction in job.changes.items():
        parts.append(f"  - {target}: {instruction}")

    if job.actor_slug:
        persona = persona_by_slug(job.actor_slug)
        if persona:
            parts.append(f"  - person on camera: {persona.casting_spec()}")
            if persona.voice_description:
                parts.append(f"  - voice: {persona.voice_description}")

    parts += [
        "",
        "REALISM: keep the base clip's camera shake, focus hunting, and lighting "
        "inconsistencies. They are what make it read as filmed rather than rendered — "
        "do not stabilise or clean them up.",
        "",
        "NEGATIVE: plastic skin, warped hands, floating objects, product morphing "
        "between frames, text drift on packaging, over-smoothed footage, cinematic "
        "colour grade, slow-motion added to real-time motion.",
    ]
    if job.notes:
        parts += ["", f"NOTES: {job.notes}"]
    return "\n".join(parts)


def create_restyle(db: Database, product_id: str, base_video: str | Path,
                   changes: dict[str, str], actor_slug: str = "", notes: str = "",
                   i_own_this_footage: bool = False) -> int:
    """Create a restyle job. Refuses without an explicit ownership attestation.

    The attestation is a real gate, not paperwork: this tool applied to someone
    else's ad is exactly the competitor-cloning workflow this project declines to
    build, and swapping the actor does not make their footage yours."""
    if not i_own_this_footage:
        raise NotYourFootage(
            "Restyling requires confirming the base video is YOURS — footage you shot, "
            "of a product you have. Restyling a competitor's ad is copying their "
            "copyrighted work (and often a real person's likeness); changing the actor "
            "and the wall does not change that. Pass i_own_this_footage=True (CLI: "
            "--i-own-this) only if it is genuinely your own footage.")
    if db.get_product(product_id) is None:
        raise ValueError(f"no product '{product_id}' — add it before restyling for it")
    path = _check_base(base_video)
    clean = validate_changes(changes)

    return db.create_restyle_job(
        product_id=product_id, base_video=str(path), changes=clean,
        actor_slug=actor_slug, notes=notes)


def load(db: Database, job_id: int) -> Optional[RestyleJob]:
    row = db.restyle_job(job_id)
    if row is None:
        return None
    return RestyleJob(
        id=row["id"], product_id=row["product_id"], base_video=row["base_video"],
        changes=row["changes"], actor_slug=row["actor_slug"], notes=row["notes"],
        status=row["status"])


def generate_restyle(db: Database, job_id: int, confirm: bool = False, mcp=None):
    """Run the restyle. Same guardrails as every other generation: approved first,
    plan persisted before the money gate, spend guards armed, disclosure stamped,
    and an unwired SDK fails cleanly instead of crashing."""
    from . import spend
    from .compliance import DISCLOSURE
    from .mcp_client import (
        ConfirmationRequired,
        GenerationNotWired,
        GenerationResult,
        HiggsfieldMCP,
    )

    job = load(db, job_id)
    if job is None:
        raise ValueError(f"no restyle job #{job_id}")
    if job.status not in ("approved", "generated"):
        raise ValueError(
            f"restyle #{job_id} is '{job.status}' — review the assembled prompt and "
            f"`restyle approve {job_id}` first. You only pay for a job you have read.")
    _check_base(job.base_video)          # the file may have moved since it was drafted

    creative = models.Creative(
        id=f"RESTYLE-{job_id}", product_id=job.product_id, format="Restyle",
        hook=(job.notes or "restyle")[:80], hook_type="restyle",
        soul_id=job.actor_slug, asset_url=None, status="briefed",
        meta={
            "aigc_disclosure": DISCLOSURE,
            "prompt": build_prompt(job),
            "base_video": job.base_video,
            "restyle_targets": sorted(job.changes),
            # Recorded so an audit can always answer "was this altered, and how?"
            "substantially_altered": True,
        },
    )
    db.upsert_creative(creative)          # plan persisted BEFORE the money gate

    existing = next((c for c in db.all_creatives() if c.id == f"RESTYLE-{job_id}"), None)
    if existing is not None and existing.status in ("generating", "ready", "exported",
                                                    "posted"):
        from .video_spec import AlreadyGenerated
        raise AlreadyGenerated(
            f"restyle #{job_id} already has a creative at '{existing.status}'"
            + (f" (job {existing.meta['job_id']})" if existing.meta.get("job_id") else "")
            + ". Generating again pays twice and overwrites the first job id. If it "
            "never landed, run `creative-recover`.")

    mcp = mcp or HiggsfieldMCP()
    if mcp.available and not confirm:
        raise ConfirmationRequired(
            f"restyle #{job_id} is ready. Generation spends credits — re-run with "
            f"--confirm.\n  SPEND IF CONFIRMED: {spend.estimate(1).render()}")

    if not mcp.available:
        return GenerationResult(
            creatives=[creative], dry_run=True,
            notes=[f"restyle #{job_id} planned (dry-run). The assembled prompt and your "
                   "base video are saved. Set HIGGSFIELD_API_KEY (+ higgsfield-client) "
                   "to run it for real."])

    spend.guard(1)
    try:
        vendor_job = mcp.submit(None, creative)      # type: ignore[arg-type]
    except NotImplementedError as e:
        raise GenerationNotWired(
            f"restyle #{job_id}: Higgsfield is configured but submit/poll isn't wired. "
            "The prompt and base path are saved as 'briefed'. A video-to-video call "
            "needs the base clip uploaded as the source — wire that in "
            f"HiggsfieldMCP.submit (it reads creative.meta['base_video']). ({e})"
        ) from e

    creative.status, creative.meta["job_id"] = "generating", vendor_job
    db.upsert_creative(creative)
    db.update_restyle_job(job_id, status="generated")
    return GenerationResult(creatives=[creative], dry_run=False,
                            notes=[f"restyle #{job_id} submitted (job {vendor_job})."])


def render_list(jobs: list[dict]) -> str:
    if not jobs:
        return ("No restyle jobs yet.\n\n"
                "Film 5–15 seconds of the real product yourself, then:\n"
                "  restyle new <product-id> <video.mp4> --change wall='warm beige' "
                "--change actor='' --actor maya --i-own-this\n\n"
                "Your footage stays the base: the product and the physics are real, "
                "and only the person and the room are generated.\n")
    lines = ["# Restyle jobs", ""]
    for j in jobs:
        targets = ", ".join(sorted(j["changes"])) or "—"
        lines.append(f"  #{j['id']:<4} {j['product_id'][:26]:26s} {j['status']:10s} "
                     f"{Path(j['base_video']).name[:24]:24s} changes: {targets}")
    lines += ["", "`restyle show <id>` for the full prompt before you spend."]
    return "\n".join(lines)


def render_guide() -> str:
    """How to shoot a base clip that restyles well."""
    return "\n".join([
        "# Filming a base clip worth restyling",
        "",
        "The restyle keeps your motion and your product and replaces everything else,",
        "so the base only needs to be RIGHT, not pretty.",
        "",
        "## Shoot",
        "  1. Vertical 9:16, phone camera, 5–15 seconds. Longer costs more and gets cut.",
        "  2. Frame the product doing the thing it is for — a pull-up bar being pulled",
        "     on, not sitting on the floor. Motion is what generated video cannot fake.",
        "  3. Plain background. The wall is going to be replaced, so give it a clean",
        "     surface to replace rather than a bookshelf it has to reconstruct.",
        "  4. Even light, no harsh backlight. Keep the natural handheld shake — it is",
        "     doing work for you.",
        "  5. Shoot 3–4 takes at different angles. One shoot, many restyles.",
        "",
        "## What changes, what does not",
        "  CHANGEABLE: " + ", ".join(CHANGEABLE),
        "  PRESERVED:  the product, the physics, the timing, and any claim.",
        "",
        "## Then",
        "  restyle new <product> <clip.mp4> --change wall='soft sage green' \\",
        "      --actor jordan --i-own-this",
        "  restyle show <id>      # read the assembled prompt — free",
        "  restyle approve <id>",
        "  restyle generate <id> --confirm",
        "",
        "One base clip → one restyle per roster actor is the honest version of",
        "demographic testing: same real product, same real motion, different person.",
        "",
        "Every output carries the AIGC label. A restyled clip is 'substantially",
        "AI-altered' under TikTok's own wording — this is exactly the case the rule",
        "was written for, so the label is not optional here.",
    ])
