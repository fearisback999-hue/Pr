"""Post from the app — the SANCTIONED way, with your per-post permission.

The operator's ask: post the finished video from the app instead of downloading it and
uploading by hand. The right way to do that is TikTok's OFFICIAL Content Posting API
(developers.tiktok.com) — the account owner authorises the app once via OAuth, and the
app can then upload on their behalf. That is a sanctioned integration, NOT a
gray-market auto-poster (those unofficial tools are the shadowban trigger this engine
warns against everywhere else).

Non-negotiable guardrails, matching the rest of the engine:
  • PER-POST PERMISSION — every post needs an explicit confirm=True. Nothing posts on
    its own; approval is your call each time (in the autopilot it's an EXTERNAL stage
    that can never be flipped to auto).
  • ONLY a generated + EXPORTED asset can be posted (it passed the AIGC-disclosure gate
    and the QA checklist). No posting a raw plan.
  • The AIGC disclosure travels with the post (the API's disclosure flag is set).
  • OFFICIAL API ONLY. Until the official credentials + OAuth token are configured, the
    upload call is an honest stub (PostingNotWired) — the engine prepares the post but
    never pretends to have published it, and never touches an unofficial endpoint.

So: with permission, the app posts for you; without the official API wired, it hands
you a ready-to-post asset and tells you exactly what's missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import CONFIG
from .db import Database, models


class PostConfirmationRequired(RuntimeError):
    """Posting was attempted without the explicit per-post confirm."""


class PostingNotWired(RuntimeError):
    """The official TikTok Content Posting API isn't configured/wired yet, so the app
    can prepare the post but not upload it. A clean signal, never a raw crash."""


@dataclass
class PostResult:
    creative_id: str
    posted: bool                       # True only on a real upload
    dry_run: bool                       # prepared but not uploaded (API not wired)
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        head = ("posted to TikTok" if self.posted else
                "prepared (not uploaded — official API not wired)")
        return f"{self.creative_id}: {head}"


def _postable(db: Database, creative_id: str) -> models.Creative:
    c = db.get_creative(creative_id) if hasattr(db, "get_creative") else None
    if c is None:
        for x in db.all_creatives():
            if x.id == creative_id:
                c = x
                break
    if c is None:
        raise ValueError(f"no creative {creative_id}")
    if c.status not in ("exported", "ready", "posted"):
        raise ValueError(
            f"{creative_id} is '{c.status}' — only a generated + EXPORTED asset can be "
            "posted (it must have cleared generation and the AIGC-disclosure export "
            "gate). Run generation, then `export-creatives`, then post.")
    if not c.meta.get("aigc_disclosure"):
        raise ValueError(
            f"{creative_id} has no AIGC disclosure in its metadata — posting is "
            "refused. The label is non-negotiable.")
    return c


def publish_creative(db: Database, creative_id: str, confirm: bool = False,
                     caption: str = "") -> PostResult:
    """Post one exported asset to TikTok via the official Content Posting API.

    Requires confirm=True (your per-post permission). Without the official API wired,
    it prepares the post and returns a dry-run result telling you what's missing — it
    never uploads through an unofficial path, and never claims to have posted."""
    c = _postable(db, creative_id)

    if not confirm:
        raise PostConfirmationRequired(
            f"{creative_id} is ready to post. Posting publishes publicly — re-run with "
            "--confirm to post it (your per-post permission).")

    if not CONFIG.tiktok_posting_available:
        return PostResult(
            creative_id=creative_id, posted=False, dry_run=True,
            notes=["official TikTok Content Posting API not configured — set "
                   "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_ACCESS_TOKEN "
                   "(OAuth-authorised by the account owner). Until then the asset is "
                   "ready; upload it yourself, or wire the official API to post from "
                   "the app. The engine will NOT use an unofficial poster."])

    # ── Official Content Posting API upload (integration point) ──────────────────
    # POST https://open.tiktokapis.com/v2/post/publish/video/init/ with the OAuth
    # access token, the video source (the exported asset), the caption, and the
    # AIGC-disclosure flag set. Poll the publish status to completion. The exact
    # request/response shape is in TikTok's official docs — wire it against a real
    # developer app rather than guessing, the same rule as the Higgsfield stub.
    raise PostingNotWired(
        f"{creative_id}: official TikTok credentials are set, but the Content Posting "
        "API call isn't wired yet. Wire publish_creative()'s upload against the "
        "official /v2/post/publish/ endpoint (the asset + caption + AIGC flag are "
        "ready). The engine refuses to guess at an unverified integration.")


def mark_posted(db: Database, creative_id: str) -> None:
    """Record that YOU posted an asset by hand (so the pipeline advances even without
    the API wired). Honest bookkeeping — it flips status to 'posted'."""
    c = _postable(db, creative_id)
    c.status = "posted"
    db.upsert_creative(c)
