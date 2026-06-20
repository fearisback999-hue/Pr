"""Supplier scoring (Part 6). Dimensions: reliability, shipping speed, quality, refund
risk, customization potential, ability to scale. A sample order is mandatory before
scaling — the model flags it, it never assumes it."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..db import models
from ..detection._stats import clamp

TARGET_SHIP_DAYS = 5.0   # sub-5-day delivery target; raw AliExpress 2–4 weeks is a refund machine


@dataclass
class SupplierScore:
    supplier: models.Supplier
    reliability: float       # 0..1
    shipping: float          # 0..1
    quality: float           # 0..1
    refund_risk_inv: float   # 0..1 (higher = lower refund risk)
    customization: float     # 0..1 (brand & defend margin)
    scalability: float       # 0..1 (MOQ, restock, inventory depth)
    total: float             # 0..100
    flags: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"{self.supplier.name or self.supplier.ref}: {self.total:.0f}/100 · "
            f"{self.supplier.ship_days:.0f}d ship · "
            f"${self.supplier.cost + self.supplier.ship_cost:.2f} landed"
            + (f" · {'; '.join(self.flags)}" if self.flags else "")
        )


def score_supplier(s: models.Supplier) -> SupplierScore:
    flags: list[str] = []

    # Reliability: rating + responsiveness.
    rating = (s.rating or 0) / 5.0
    responsiveness = 1 - clamp((s.response_hrs or 24) / 48, 0, 1)
    reliability = clamp(0.6 * rating + 0.4 * responsiveness, 0, 1)

    # Shipping speed vs the sub-5-day target.
    shipping = clamp((10 - s.ship_days) / (10 - TARGET_SHIP_DAYS), 0, 1)
    if s.ship_days > TARGET_SHIP_DAYS:
        flags.append(f"ship {s.ship_days:.0f}d > {TARGET_SHIP_DAYS:.0f}d target")
    if not s.us_warehouse and s.ship_days > 7:
        flags.append("no US warehouse — refund risk")

    # Quality proxy from notes (a real pass would read review NLP / sample results).
    notes = (s.quality_notes or "").lower()
    quality = 0.5
    if any(w in notes for w in ("excellent", "great", "high quality", "sample passed")):
        quality = 0.85
    elif any(w in notes for w in ("poor", "fragile", "complaints", "defect")):
        quality = 0.25
    flags.append("SAMPLE ORDER required before scaling")  # always — Part 6 mandate

    # Refund risk inverse from US warehouse + ship speed (fast, local → fewer refunds).
    refund_risk_inv = clamp(0.5 * shipping + 0.5 * (1.0 if s.us_warehouse else 0.3), 0, 1)

    # Customization: can you brand it and defend margin?
    customization = 0.7 if any(w in notes for w in ("custom", "private label", "oem")) else 0.4

    # Scalability: low MOQ + US warehouse = easy to scale without huge cash lock-up.
    moq_factor = 1 - clamp((s.moq - 1) / 500, 0, 1)
    scalability = clamp(0.6 * moq_factor + 0.4 * (1.0 if s.us_warehouse else 0.4), 0, 1)
    if s.moq > 200:
        flags.append(f"high MOQ ({s.moq}) — cash lock-up")

    total = round(100 * (
        0.22 * reliability + 0.25 * shipping + 0.18 * quality
        + 0.15 * refund_risk_inv + 0.08 * customization + 0.12 * scalability
    ), 1)

    return SupplierScore(
        supplier=s, reliability=reliability, shipping=shipping, quality=quality,
        refund_risk_inv=refund_risk_inv, customization=customization,
        scalability=scalability, total=total, flags=flags,
    )


def rank_suppliers(suppliers: list[models.Supplier]) -> list[SupplierScore]:
    return sorted((score_supplier(s) for s in suppliers), key=lambda x: x.total, reverse=True)
