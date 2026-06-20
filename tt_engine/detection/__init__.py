"""Part 2 — detection core: the repeatable edge.

Detect steep sales acceleration while competition is still low, then move before the
window closes (Part 0, truth #1). The pieces:

  momentum   — slope + acceleration of sales; 7-day vs 30-day velocity
  saturation — seller / promo-video / ad counts + ad-age (flood of fresh ads = closing)
  trigger    — fires on HIGH momentum + LOW-but-rising saturation, and always emits a
               window_days runway estimate ("good product, ~18 days of runway")
  confirm    — cross-confirm a trigger across two velocity sources before trusting it
"""

from .confirm import CrossConfirmation, confirm_metrics, cross_confirm
from .momentum import MomentumResult, compute_momentum
from .saturation import SaturationResult, compute_saturation
from .trigger import TriggerResult, evaluate

__all__ = [
    "MomentumResult", "compute_momentum",
    "SaturationResult", "compute_saturation",
    "TriggerResult", "evaluate",
    "CrossConfirmation", "cross_confirm", "confirm_metrics",
]
