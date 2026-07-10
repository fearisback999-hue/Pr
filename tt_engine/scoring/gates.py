"""Hard gates (Part 3) — auto-disqualify regardless of total.

  • margin below ~45%
  • any return-risk red flag
  • branded / trademarked item
  • restricted TikTok category
  • commodity-saturated (already a crowded red ocean)

A hot momentum score must never override an economic, compliance, or saturation landmine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..economics.calculator import MARGIN_FLOOR
from .inputs import ScoringInputs

RETURN_RISK_RED_FLAG = 0.10  # return rate at/above which the gate trips
# Saturation index at/above which the opportunity is a crowded commodity — skip it without
# a structural edge. Grounded in the common research rule of thumb: products scoring above
# ~65% on a saturation scale are red-ocean and not worth entering cold (2026-07-09).
COMMODITY_SATURATION_MAX = 65.0


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
    sat_index = inp.trigger.saturation.index
    if sat_index >= COMMODITY_SATURATION_MAX:
        failures.append(
            f"commodity-saturated (saturation {sat_index:.0f} ≥ {COMMODITY_SATURATION_MAX:.0f}) "
            "— crowded red ocean; skip without a structural edge"
        )

    return GateResult(passed=not failures, failures=failures)
