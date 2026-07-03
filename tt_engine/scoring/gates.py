"""Hard gates (Part 3) — auto-disqualify regardless of total.

  • margin below ~45%
  • any return-risk red flag
  • branded / trademarked item
  • restricted TikTok category

A hot momentum score must never override an economic or compliance landmine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..economics.calculator import MARGIN_FLOOR
from .inputs import ScoringInputs

RETURN_RISK_RED_FLAG = 0.10  # return rate at/above which the gate trips


@dataclass
class GateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def check_gates(inp: ScoringInputs) -> GateResult:
    failures: list[str] = []

    if not inp.economics.landed_known:
        failures.append(
            "no real landed cost on file — margin unverifiable (add a supplier: `add-supplier`)"
        )
    elif inp.economics.gross_margin < MARGIN_FLOOR:
        failures.append(
            f"margin {inp.economics.gross_margin*100:.0f}% below {MARGIN_FLOOR*100:.0f}% floor"
        )
    rr = inp.economics.return_rate
    if rr is not None and rr >= RETURN_RISK_RED_FLAG:
        failures.append(f"return-risk red flag ({rr*100:.0f}% ≥ {RETURN_RISK_RED_FLAG*100:.0f}%)")
    if inp.product.branded:
        failures.append("branded / trademarked item")
    if inp.product.restricted:
        failures.append("restricted TikTok category")

    return GateResult(passed=not failures, failures=failures)
