"""Shop Performance Score proxy. A real score comes from TikTok Seller Center; this models
the three levers the brief calls out — shipping speed, refund rate, service response time —
so the engine can warn *before* reach gets throttled. Handle service personally early
(Part 10): it's where you learn what people actually complain about, which feeds straight
back into product selection and return-risk scoring."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..detection._stats import clamp

THROTTLE_THRESHOLD = 70.0     # below this, reach starts getting throttled
SUSPENSION_THRESHOLD = 50.0   # below this you're in suspension territory — store-ending

# Hard limits the brief implies (sub-5-day fulfillment, refunds under control).
SHIP_OK_DAYS = 3.0
SHIP_BAD_DAYS = 10.0
REFUND_BAD = 0.10
RESPONSE_BAD_HRS = 48.0


@dataclass
class AccountHealth:
    ship_days: float
    refund_rate: float
    response_hrs: float
    shipping_score: float        # 0..1
    refund_score: float          # 0..1
    service_score: float         # 0..1
    score: float                 # 0..100 (Shop Performance proxy)
    at_risk: bool                # below the throttle threshold
    critical: bool               # below the suspension threshold
    warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        state = "CRITICAL" if self.critical else ("AT RISK" if self.at_risk else "healthy")
        head = (
            f"Shop health {self.score:.0f}/100 [{state}] · "
            f"{self.ship_days:.0f}d ship · {self.refund_rate*100:.0f}% refunds · "
            f"{self.response_hrs:.0f}h response"
        )
        if self.warnings:
            head += "\n  ⚠️ " + "\n  ⚠️ ".join(self.warnings)
        return head


def assess_health(ship_days: float, refund_rate: float, response_hrs: float) -> AccountHealth:
    # Each lever maps to 0..1 (1 = excellent).
    shipping = clamp((SHIP_BAD_DAYS - ship_days) / (SHIP_BAD_DAYS - SHIP_OK_DAYS), 0, 1)
    refund = 1 - clamp(refund_rate / REFUND_BAD, 0, 1)
    service = 1 - clamp(response_hrs / RESPONSE_BAD_HRS, 0, 1)
    # Shipping + refunds dominate the Shop Performance Score; service matters but less.
    score = round(100 * (0.4 * shipping + 0.4 * refund + 0.2 * service), 1)

    at_risk = score < THROTTLE_THRESHOLD
    critical = score < SUSPENSION_THRESHOLD

    warnings: list[str] = []
    if ship_days > 5:
        warnings.append(f"ship time {ship_days:.0f}d > 5d — slow fulfillment drives refunds")
    if refund_rate >= REFUND_BAD:
        warnings.append(f"refund rate {refund_rate*100:.0f}% ≥ {REFUND_BAD*100:.0f}% — tanks the score")
    if response_hrs > 24:
        warnings.append(f"service response {response_hrs:.0f}h > 24h — answer customers faster")
    if critical:
        warnings.append("CRITICAL: near suspension territory — one suspension and the store is gone")
    elif at_risk:
        warnings.append("reach is being throttled — fix the levers above before scaling spend")

    return AccountHealth(
        ship_days=ship_days, refund_rate=refund_rate, response_hrs=response_hrs,
        shipping_score=shipping, refund_score=refund, service_score=service,
        score=score, at_risk=at_risk, critical=critical, warnings=warnings,
    )
