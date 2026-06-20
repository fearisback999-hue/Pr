"""Part 8 — Distribution. You need two channels, not one: paid ads (your Higgsfield
creatives, tested in volume) AND the creator/affiliate program — the native distribution
engine of TikTok Shop, which on many winning shops drives more sales than paid ads.

Automate finding creators and the sample-seeding logistics. Do NOT automate the
relationship or the outreach copy — spammy automated outreach performs badly and burns
the channel."""

from .affiliate import (
    OUTREACH_PRINCIPLES,
    CreatorProspect,
    SeedingPlan,
    build_seeding_plan,
    rank_creators,
    score_creator,
)

__all__ = [
    "CreatorProspect", "SeedingPlan", "score_creator", "rank_creators",
    "build_seeding_plan", "OUTREACH_PRINCIPLES",
]
