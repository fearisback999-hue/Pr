"""Part 3 — Product Scoring Algorithm (100 points).

Six sub-scores, each computed from data, plus hard gates that auto-disqualify regardless
of total. Recommend only products scoring ≥ 80 that also clear every gate. A hot momentum
score must never override an economic or compliance landmine.
"""

from .algorithm import DEFAULT_WEIGHTS, load_weights, save_weights, score_product
from .gates import GateResult, check_gates
from .inputs import ContentSignals, ScoringInputs

__all__ = [
    "ScoringInputs", "ContentSignals", "GateResult", "check_gates",
    "score_product", "load_weights", "save_weights", "DEFAULT_WEIGHTS",
]
