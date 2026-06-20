"""Everything the scorer needs, bundled. Detection + economics are required; the rest
have heuristic defaults so the engine scores offline, and accept overrides from real
vision/LLM/trend passes when you have them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..db import models
from ..detection import TriggerResult
from ..economics import Economics


@dataclass
class ContentSignals:
    """Optional vision/LLM-derived signals for the Viral Demonstration sub-score (Part 3.1).
    Each is a 0..1 confidence; None means 'use the category heuristic'."""
    three_second_clarity: Optional[float] = None   # readable in 3s from a vision pass on top videos
    curiosity_interrupt: Optional[float] = None     # pattern interrupt / scroll-stop
    visible_result: Optional[float] = None          # before/after or demonstrable result
    emotional_reaction: Optional[float] = None      # provokes a reaction
    distinct_angles: Optional[int] = None           # count of distinct creative angles


@dataclass
class ScoringInputs:
    product: models.Product
    trigger: TriggerResult
    economics: Economics
    # Optional external signals — defaults applied when absent.
    search_trend_slope: Optional[float] = None      # -1..1, upstream demand (Google Trends)
    category_momentum: Optional[float] = None       # 0..1, category-level demand trend
    urgency_signal: Optional[float] = None          # 0..1, urgency / repeat-purchase pull
    content: ContentSignals = None                  # type: ignore[assignment]

    def __post_init__(self):
        if self.content is None:
            self.content = ContentSignals()
