"""Creator / affiliate funnel (Part 8). Score and rank prospects, plan sample seeding at
volume (a tool like Shoplus does outreach logistics). The outreach *copy* and the
relationship stay human — this module deliberately does not generate messages."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..detection._stats import clamp

# Guardrails surfaced to the operator — the channel is relationship-driven.
OUTREACH_PRINCIPLES = [
    "Write every first message yourself. Reference the creator's actual content.",
    "Never blast identical copy — it reads as spam and burns the channel.",
    "Lead with the free sample and a clear commission, not a hard ask.",
    "Keep replies human and fast; a real relationship out-earns any template.",
]


@dataclass
class CreatorProspect:
    handle: str
    followers: int
    niche: str
    engagement_rate: float          # 0..1 (e.g. 0.06 = 6%)
    avg_views: int = 0
    shop_gmv_signal: float = 0.0    # 0..1, prior shop-driving evidence if known


@dataclass
class ScoredCreator:
    prospect: CreatorProspect
    fit: float                      # niche/category fit 0..1
    reach: float                    # 0..1
    conversion_signal: float        # 0..1 (engagement + prior GMV)
    score: float                    # 0..100

    @property
    def summary(self) -> str:
        p = self.prospect
        return (f"@{p.handle} · {p.followers:,} followers · {p.engagement_rate*100:.1f}% eng · "
                f"{p.niche} · {self.score:.0f}/100")


@dataclass
class SeedingPlan:
    product_id: str
    targets: list[ScoredCreator]
    samples_to_send: int
    principles: list[str] = field(default_factory=lambda: list(OUTREACH_PRINCIPLES))

    @property
    def summary(self) -> str:
        return (f"Seed {self.samples_to_send} samples to top creators for {self.product_id}; "
                f"write each outreach by hand.")


def score_creator(p: CreatorProspect, category: str) -> ScoredCreator:
    fit = 1.0 if p.niche.lower() == category.lower() else 0.4
    # Reach on a log-ish scale: ~500k followers → strong.
    reach = clamp(math.log10(max(p.followers, 1)) / math.log10(500_000), 0, 1)
    conversion = clamp(0.6 * clamp(p.engagement_rate / 0.10, 0, 1) + 0.4 * p.shop_gmv_signal, 0, 1)
    score = round(100 * (0.4 * fit + 0.3 * reach + 0.3 * conversion), 1)
    return ScoredCreator(prospect=p, fit=fit, reach=reach, conversion_signal=conversion, score=score)


def rank_creators(prospects: list[CreatorProspect], category: str) -> list[ScoredCreator]:
    return sorted((score_creator(p, category) for p in prospects),
                  key=lambda s: s.score, reverse=True)


def build_seeding_plan(
    product_id: str,
    prospects: list[CreatorProspect],
    category: str,
    samples: int = 10,
) -> SeedingPlan:
    ranked = rank_creators(prospects, category)
    return SeedingPlan(
        product_id=product_id, targets=ranked[:samples],
        samples_to_send=min(samples, len(ranked)),
    )
