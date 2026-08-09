"""Spend guards for generation — the money side of the confirm gate.

The confirm gate answers "did you agree to spend?" It never answered "how much?"
This module answers the second question, and puts hard ceilings under it.

Three protections, in the order they fire:

  1. SIZE CAP — a batch is clamped to MAX_BATCH. `--variations 3000` is a typo,
     not an instruction, and without this it submits 3,000 paid jobs.
  2. COST ESTIMATE — with TT_GENERATION_UNIT_COST set, every confirm prompt shows
     the dollar figure BEFORE you approve. You cannot consent to an unknown number.
  3. SPEND CEILING — with TT_MAX_BATCH_SPEND set, a batch whose estimate exceeds
     the ceiling is refused outright, even with --confirm. The ceiling exists for
     the moment you are tired and typing fast.

Unit cost is deliberately NOT guessed. Higgsfield prices in credits and the
credit-to-dollar rate depends on your plan, so a hardcoded default would be a
made-up number in a file whose entire job is to prevent made-up numbers (the
same rule as Economics' no-placeholder-cost). Unset → the estimate says
"unpriced" and tells you which variable to set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Higgsfield's documented batch range is 20–100 variations. 100 is the ceiling a
# real batch ever needs; anything above it is a fat-finger.
MAX_BATCH = 100
MIN_BATCH = 1


class BatchTooLarge(ValueError):
    """Requested variation count is above MAX_BATCH."""


class SpendCeilingExceeded(RuntimeError):
    """The batch's estimated cost is over TT_MAX_BATCH_SPEND — refused even with confirm."""


def _float_env(name: str) -> Optional[float]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def unit_cost() -> Optional[float]:
    """Dollars per generated clip, or None if you haven't told us. Never guessed."""
    return _float_env("TT_GENERATION_UNIT_COST")


def spend_ceiling() -> Optional[float]:
    """Hard per-batch dollar ceiling, or None for no ceiling."""
    return _float_env("TT_MAX_BATCH_SPEND")


@dataclass(frozen=True)
class Estimate:
    count: int
    unit: Optional[float]
    ceiling: Optional[float]

    @property
    def total(self) -> Optional[float]:
        return None if self.unit is None else round(self.count * self.unit, 2)

    @property
    def priced(self) -> bool:
        return self.total is not None

    @property
    def over_ceiling(self) -> bool:
        return (self.ceiling is not None and self.total is not None
                and self.total > self.ceiling)

    def render(self) -> str:
        """The line a human reads before approving a spend."""
        if not self.priced:
            return (f"{self.count} clip(s) — cost UNPRICED. Set TT_GENERATION_UNIT_COST "
                    "to your real per-clip cost and this shows dollars before you "
                    "approve, instead of after.")
        line = f"{self.count} clip(s) × ${self.unit:,.2f} = ~${self.total:,.2f}"
        if self.ceiling is not None:
            line += f"  (ceiling ${self.ceiling:,.2f})"
        # At the engine's own ~1-in-4 keep rate, the honest unit is cost-per-USABLE.
        from .realism import USABLE_CLIP_RATE
        if USABLE_CLIP_RATE > 0:
            per_usable = self.total / max(1.0, self.count * USABLE_CLIP_RATE)
            line += f"\n  ≈ ${per_usable:,.2f} per USABLE clip at the {USABLE_CLIP_RATE:.0%} keep rate"
        return line


def clamp_variations(n: int) -> int:
    """Validate a requested batch size. Raises rather than silently shrinking —
    a silently-shrunk batch hides the typo that caused it."""
    if n < MIN_BATCH:
        raise BatchTooLarge(f"variations must be at least {MIN_BATCH} (got {n})")
    if n > MAX_BATCH:
        raise BatchTooLarge(
            f"{n} variations is above the {MAX_BATCH} cap. A real batch is 20–100; "
            f"{n} is almost certainly a typo, and it would submit {n} paid jobs. "
            f"Re-run with --variations {MAX_BATCH} or lower if you meant it.")
    return n


def estimate(count: int) -> Estimate:
    return Estimate(count=count, unit=unit_cost(), ceiling=spend_ceiling())


def guard(count: int) -> Estimate:
    """Full preflight for a spend: size cap, then estimate, then ceiling.

    Called on the confirmed path only — planning and dry-runs are free and
    should never be blocked by a spend guard."""
    clamp_variations(count)
    est = estimate(count)
    if est.over_ceiling:
        raise SpendCeilingExceeded(
            f"batch would cost ~${est.total:,.2f}, over your TT_MAX_BATCH_SPEND "
            f"ceiling of ${est.ceiling:,.2f}. Nothing was submitted. Lower the batch "
            "size, or raise the ceiling deliberately if this spend is intended.")
    return est
