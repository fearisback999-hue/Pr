"""Assemble the 100-point score: weight each sub-score, apply the hard gates, and emit a
models.Score plus a per-component breakdown for the report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Optional

from ..config import CONFIG
from ..db import models
from .gates import GateResult, check_gates
from .inputs import ScoringInputs
from .subscores import SUBSCORES

_WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.json"

DEFAULT_WEIGHTS = {
    "viral_demo": 20.0,
    "market_demand": 20.0,
    "competition_timing": 15.0,
    "economics": 20.0,
    "content_potential": 15.0,
    "brand_potential": 10.0,
}


def load_weights() -> dict[str, float]:
    if _WEIGHTS_PATH.exists():
        try:
            return {k: float(v) for k, v in json.loads(_WEIGHTS_PATH.read_text()).items()}
        except (json.JSONDecodeError, ValueError):
            pass
    return dict(DEFAULT_WEIGHTS)


def save_weights(weights: dict[str, float]) -> None:
    _WEIGHTS_PATH.write_text(json.dumps(weights, indent=2) + "\n")


@dataclass
class ScoreBreakdown:
    score: models.Score
    gate: GateResult
    category_points: dict[str, float] = field(default_factory=dict)   # category -> points
    components: dict[str, dict[str, float]] = field(default_factory=dict)  # category -> {comp: pts}
    weights: dict[str, float] = field(default_factory=dict)

    @property
    def recommended(self) -> bool:
        """Surface only ≥ threshold AND gates clear (Part 3). The bar is CONFIG.score_threshold
        (default 80, the brief's recommendation), so an operator override flows through here."""
        return self.score.gates_passed and self.score.total >= CONFIG.score_threshold


def score_product(
    inp: ScoringInputs,
    weights: Optional[dict[str, float]] = None,
    on_date: Optional[str] = None,
) -> ScoreBreakdown:
    weights = weights or load_weights()
    on_date = on_date or _date.today().isoformat()

    category_points: dict[str, float] = {}
    components: dict[str, dict[str, float]] = {}
    for name, fn in SUBSCORES.items():
        fraction, breakdown = fn(inp)
        w = weights.get(name, DEFAULT_WEIGHTS[name])
        category_points[name] = round(fraction * w, 2)
        components[name] = breakdown

    total = round(sum(category_points.values()), 2)
    gate = check_gates(inp)

    score = models.Score(
        product_id=inp.product.id, date=on_date,
        viral_demo=category_points["viral_demo"],
        market_demand=category_points["market_demand"],
        competition_timing=category_points["competition_timing"],
        economics=category_points["economics"],
        content_potential=category_points["content_potential"],
        brand_potential=category_points["brand_potential"],
        total=total, gates_passed=gate.passed, gate_failures=gate.failures,
        window_days=inp.trigger.window_days,
    )
    return ScoreBreakdown(
        score=score, gate=gate, category_points=category_points,
        components=components, weights=weights,
    )
