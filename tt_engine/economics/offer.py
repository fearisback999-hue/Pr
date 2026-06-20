"""The offer is part of product selection (Part 5). Price point, bundle, free-shipping
threshold, and upsell all change the margin math — model them, then decide by hand."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .calculator import Economics, compute_economics


@dataclass
class Offer:
    bundle_qty: int = 1                  # units per order (3-pack, etc.)
    bundle_price: Optional[float] = None # total price for the bundle (overrides per-unit * qty)
    free_ship_threshold: float = 0.0     # absorb shipping above this order value
    upsell_take_rate: float = 0.0        # fraction of orders that add the upsell
    upsell_margin: float = 0.0           # extra gross profit per upsell taken


def apply_offer(
    offer: Offer,
    unit_sell_price: float,
    supplier_cost: float,
    ship_cost: float = 0.0,
    return_rate: Optional[float] = None,
) -> Economics:
    """Recompute economics at the order (basket) level for a given offer structure.

    Returns an Economics where `sell_price` is the basket price, costs are scaled to the
    bundle quantity, and the expected upsell contribution is folded into gross profit.
    """
    qty = max(1, offer.bundle_qty)
    basket_price = offer.bundle_price if offer.bundle_price else unit_sell_price * qty
    basket_supplier = supplier_cost * qty
    # Free shipping is a cost you eat above the threshold.
    basket_ship = 0.0 if basket_price >= offer.free_ship_threshold > 0 else ship_cost * qty

    econ = compute_economics(
        sell_price=basket_price,
        supplier_cost=basket_supplier,
        ship_cost=basket_ship,
        return_rate=return_rate,
    )
    # Fold in expected upsell profit (added straight to per-order gross profit).
    if offer.upsell_take_rate and offer.upsell_margin:
        extra = offer.upsell_take_rate * offer.upsell_margin
        gp = econ.gross_profit + extra
        margin = gp / basket_price if basket_price else 0.0
        breakeven = basket_price / gp if gp > 0 else float("inf")
        econ = Economics(
            sell_price=econ.sell_price, supplier_cost=econ.supplier_cost,
            ship_cost=econ.ship_cost, fee_rate=econ.fee_rate, landed_cost=econ.landed_cost,
            fee=econ.fee, gross_profit=gp, gross_margin=margin, breakeven_roas=breakeven,
            max_cac=max(gp, 0.0), return_rate=econ.return_rate,
            profit_after_returns=econ.profit_after_returns,
        )
    return econ
