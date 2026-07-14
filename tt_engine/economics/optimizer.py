"""Profit optimizer: the FULL fee stack, an honest offer sweep, and a leak check
against your actual test logs.

Why this exists: the core engine (deliberately) scores against TikTok's 6% referral fee
only — the number every product shares. But YOUR true take-rate also includes payment
processing (researched range ~1–3.8% of order value, 2026-07) and whatever affiliate
commission you set (a choice, 5–50%). A product that clears the 45% gate at 6% fees can
quietly lose money at the real stack. This module recomputes everything at the true
stack and shows the delta.

What the offer sweep does NOT do: pretend to know demand elasticity. Nobody knows how
conversion changes at $34.99 vs $39.99 until you test it. The sweep shows the exact
profit/break-even math at each price and bundle inside your constraints (impulse band,
margin floor) and ranks by profit-per-order — the decision stays yours, informed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..db import models
from .calculator import FEE_RATE, MARGIN_FLOOR, Economics, compute_economics

# Researched July 2026 (TikTok Seller Center fee docs + fee guides; reverify — fee
# schedules change): payment processing runs ~1–3.8% of order value depending on volume
# and card mix. 3% is the conservative planning default; override with the actual rate
# from your settlement statements once you have them.
DEFAULT_PAYMENT_RATE = 0.03
IMPULSE_LO, IMPULSE_HI = 15.0, 50.0   # matches the scorer's impulse price band


@dataclass
class TrueEconomics:
    base: Economics                  # the 6%-referral-only view the scorer uses
    payment_rate: float
    affiliate_rate: float
    true_fee: float                  # referral + payment + affiliate, in $
    true_profit: float               # gross profit after the FULL stack
    true_margin: float
    true_breakeven_roas: float
    true_max_cac: float

    @property
    def summary(self) -> str:
        b = self.base
        return (
            f"6%-only view: {b.gross_margin*100:.0f}% margin · break-even {b.breakeven_roas:.2f}\n"
            f"TRUE stack ({FEE_RATE*100:.0f}% referral + {self.payment_rate*100:.1f}% payment"
            f" + {self.affiliate_rate*100:.0f}% affiliate): {self.true_margin*100:.0f}% margin"
            f" · profit ${self.true_profit:.2f}/unit · break-even {self.true_breakeven_roas:.2f}"
            f" · max CAC ${self.true_max_cac:.2f}"
        )


def true_economics(
    sell_price: float,
    supplier_cost: float,
    ship_cost: float = 0.0,
    payment_rate: float = DEFAULT_PAYMENT_RATE,
    affiliate_rate: float = 0.0,
    return_rate: Optional[float] = None,
) -> TrueEconomics:
    """The full stack. affiliate_rate is the commission you set (0 for pure-paid/organic
    sales — but remember affiliate-driven orders pay it on top of everything else)."""
    base = compute_economics(sell_price, supplier_cost, ship_cost, return_rate=return_rate)
    extra = sell_price * (payment_rate + affiliate_rate)
    true_fee = base.fee + extra
    true_profit = base.gross_profit - extra
    true_margin = true_profit / sell_price if sell_price else 0.0
    return TrueEconomics(
        base=base, payment_rate=payment_rate, affiliate_rate=affiliate_rate,
        true_fee=round(true_fee, 2), true_profit=round(true_profit, 2),
        true_margin=round(true_margin, 4),
        true_breakeven_roas=round(sell_price / true_profit, 2) if true_profit > 0 else float("inf"),
        true_max_cac=round(max(true_profit, 0.0), 2),
    )


@dataclass
class OfferOption:
    label: str
    order_price: float               # what the buyer pays per order
    units: int
    true_margin: float
    true_profit_per_order: float
    true_breakeven_roas: float
    in_impulse_band: bool
    above_floor: bool

    @property
    def viable(self) -> bool:
        return self.above_floor and self.true_profit_per_order > 0

    @property
    def line(self) -> str:
        flags = []
        if not self.above_floor:
            flags.append(f"below {MARGIN_FLOOR*100:.0f}% floor")
        if not self.in_impulse_band:
            flags.append("outside $15–50 impulse band")
        tail = ("  ⚠ " + ", ".join(flags)) if flags else ""
        return (f"{self.label:<28} ${self.order_price:>7.2f}/order · "
                f"margin {self.true_margin*100:>3.0f}% · profit ${self.true_profit_per_order:>6.2f} · "
                f"break-even {self.true_breakeven_roas:.2f}{tail}")


@dataclass
class OptimizerReport:
    product_id: str
    current: TrueEconomics
    options: list[OfferOption] = field(default_factory=list)
    recommendation: Optional[OfferOption] = None
    leaks: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# Profit optimizer — {self.product_id}",
            "",
            "## True take-rate (the number the scorer's 6%-only view understates)",
            "",
            self.current.summary,
            "",
            "## Offer sweep (math per option — demand elasticity is NOT modeled;",
            "## you learn conversion by testing, this shows what each test must beat)",
            "",
            *[f"  {'★ ' if o is self.recommendation else '  '}{o.line}" for o in self.options],
            "",
        ]
        if self.recommendation:
            r = self.recommendation
            lines += [
                f"**Recommended structure: {r.label}** — highest profit/order that stays "
                f"inside the impulse band and above the margin floor at the TRUE fee "
                f"stack. Your ads must beat ROAS {r.true_breakeven_roas:.2f} on this "
                "structure to make money.",
                "",
            ]
        else:
            lines += ["**No offer structure clears the margin floor at the true fee "
                      "stack.** Renegotiate the supplier cost or drop the product — "
                      "don't launch into guaranteed negative margin.", ""]
        if self.leaks:
            lines += ["## Profit leaks & reality checks", ""]
            lines += [f"- {leak}" for leak in self.leaks]
        return "\n".join(lines) + "\n"


def optimize_offer(
    product_id: str,
    sell_price: float,
    supplier_cost: float,
    ship_cost: float = 0.0,
    payment_rate: float = DEFAULT_PAYMENT_RATE,
    affiliate_rate: float = 0.15,
    return_rate: Optional[float] = None,
    tests: Sequence[models.Test] = (),
) -> OptimizerReport:
    """Sweep single-unit price points and bundle structures at the TRUE fee stack.
    Bundles reuse the researched pattern: 2-pack ≈ 1.7–1.8× unit price, 3-pack ≈ 2.4×."""
    current = true_economics(sell_price, supplier_cost, ship_cost,
                             payment_rate, affiliate_rate, return_rate)

    options: list[OfferOption] = []
    # Single-unit price grid: −20% … +30% of current price.
    for mult in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3):
        price = round(sell_price * mult, 2)
        te = true_economics(price, supplier_cost, ship_cost,
                            payment_rate, affiliate_rate, return_rate)
        options.append(OfferOption(
            label=f"single @ {mult:.0%} price", order_price=price, units=1,
            true_margin=te.true_margin, true_profit_per_order=te.true_profit,
            true_breakeven_roas=te.true_breakeven_roas,
            in_impulse_band=IMPULSE_LO <= price <= IMPULSE_HI,
            above_floor=te.true_margin >= MARGIN_FLOOR,
        ))
    # Bundles at the current unit price.
    for qty, mult, label in ((2, 1.75, "2-pack @ 1.75× unit"),
                             (3, 2.40, "3-pack @ 2.40× unit")):
        price = round(sell_price * mult, 2)
        te = true_economics(price, supplier_cost * qty, ship_cost * qty,
                            payment_rate, affiliate_rate, return_rate)
        options.append(OfferOption(
            label=label, order_price=price, units=qty,
            true_margin=te.true_margin, true_profit_per_order=te.true_profit,
            true_breakeven_roas=te.true_breakeven_roas,
            in_impulse_band=IMPULSE_LO <= price <= IMPULSE_HI,
            above_floor=te.true_margin >= MARGIN_FLOOR,
        ))

    viable_in_band = [o for o in options if o.viable and o.in_impulse_band]
    rec = max(viable_in_band, key=lambda o: o.true_profit_per_order) if viable_in_band else None

    leaks: list[str] = []
    if current.base.gross_margin >= MARGIN_FLOOR > current.true_margin:
        leaks.append(
            f"THE BIG ONE: this product clears the {MARGIN_FLOOR*100:.0f}% gate at the "
            f"6%-only view ({current.base.gross_margin*100:.0f}%) but NOT at the true "
            f"stack ({current.true_margin*100:.0f}%) — affiliate-driven orders lose money "
            "at this price")
    fee_delta = current.true_breakeven_roas - current.base.breakeven_roas
    if fee_delta > 0 and current.true_breakeven_roas != float("inf"):
        leaks.append(
            f"true break-even ROAS is {current.true_breakeven_roas:.2f}, not "
            f"{current.base.breakeven_roas:.2f} — judge every ad against the higher bar "
            f"(+{fee_delta:.2f})")
    if tests:
        priced = [t for t in tests if t.roas is not None and t.spend > 0]
        if priced:
            spend = sum(t.spend for t in priced)
            revenue = sum(t.spend * t.roas for t in priced)
            actual = revenue / spend if spend else 0.0
            verdict = ("ABOVE" if actual >= current.true_breakeven_roas else "BELOW")
            leaks.append(
                f"actuals: blended ROAS {actual:.2f} over ${spend:.0f} logged spend — "
                f"{verdict} the true break-even {current.true_breakeven_roas:.2f}"
                + ("" if verdict == "ABOVE" else " — you are currently paying to sell"))
    if return_rate:
        per_return_cost = current.true_profit + supplier_cost + ship_cost
        leaks.append(
            f"each return costs ~${per_return_cost:.2f} (lost profit + eaten landed "
            f"cost); at {return_rate*100:.0f}% return rate that's "
            f"${per_return_cost * return_rate:.2f}/order of silent drag")
    leaks.append("payment rate here is the conservative research default "
                 f"({payment_rate*100:.1f}%) — replace with the real rate from your "
                 "settlement statement once you have one (override: --payment)")

    return OptimizerReport(product_id=product_id, current=current,
                           options=options, recommendation=rec, leaks=leaks)
