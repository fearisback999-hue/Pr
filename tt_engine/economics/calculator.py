"""The unit economics. Every number here is computed from inputs — nothing guessed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

FEE_RATE = 0.06        # TikTok Shop fee (Part 5)
MARGIN_FLOOR = 0.45    # hard floor — below this the product is disqualified (Part 3 gate)
MARGIN_TARGET = 0.60   # aim here or better


@dataclass
class Economics:
    sell_price: float
    supplier_cost: float
    ship_cost: float
    fee_rate: float
    landed_cost: float          # supplier + shipping
    fee: float                  # fee_rate * sell_price
    gross_profit: float         # sell_price − landed_cost − fee
    gross_margin: float         # gross_profit / sell_price
    breakeven_roas: float       # sell_price / gross_profit (what ads must return to not lose)
    max_cac: float              # = gross_profit; spend more to acquire and you lose per sale
    return_rate: Optional[float] = None
    profit_after_returns: Optional[float] = None  # expected gross profit net of refunds
    landed_known: bool = True   # False = no real supplier cost on file → refuse to score

    @property
    def meets_floor(self) -> bool:
        return self.landed_known and self.gross_margin >= MARGIN_FLOOR

    @property
    def summary(self) -> str:
        if not self.landed_known:
            return (f"${self.sell_price:.2f} sell · landed cost UNKNOWN — economics not "
                    f"scored (add a real supplier cost: `add-supplier`)")
        s = (
            f"${self.sell_price:.2f} sell · ${self.landed_cost:.2f} landed · "
            f"{self.gross_margin*100:.0f}% margin · ${self.gross_profit:.2f} profit/unit · "
            f"break-even ROAS {self.breakeven_roas:.2f} · max CAC ${self.max_cac:.2f}"
        )
        if self.return_rate is not None:
            s += f" · returns {self.return_rate*100:.0f}%"
        return s


def unknown_economics(sell_price: float, return_rate: Optional[float] = None) -> Economics:
    """No real landed cost on file. Every derived number is zeroed rather than guessed —
    the scorer refuses to score Economics and the margin gate fails as unverifiable."""
    return Economics(
        sell_price=sell_price, supplier_cost=0.0, ship_cost=0.0, fee_rate=FEE_RATE,
        landed_cost=0.0, fee=0.0, gross_profit=0.0, gross_margin=0.0,
        breakeven_roas=float("inf"), max_cac=0.0, return_rate=return_rate,
        profit_after_returns=None, landed_known=False,
    )


def compute_economics(
    sell_price: float,
    supplier_cost: float,
    ship_cost: float = 0.0,
    fee_rate: float = FEE_RATE,
    return_rate: Optional[float] = None,
) -> Economics:
    landed_cost = supplier_cost + ship_cost
    fee = sell_price * fee_rate
    gross_profit = sell_price - landed_cost - fee
    gross_margin = gross_profit / sell_price if sell_price else 0.0
    # Break-even ROAS and max CAC are undefined/meaningless when profit ≤ 0.
    breakeven_roas = sell_price / gross_profit if gross_profit > 0 else float("inf")
    max_cac = max(gross_profit, 0.0)

    profit_after_returns = None
    if return_rate is not None:
        # A refund loses the gross profit and (typically) the landed cost on that unit.
        loss_per_return = gross_profit + landed_cost
        profit_after_returns = gross_profit - return_rate * loss_per_return

    return Economics(
        sell_price=sell_price, supplier_cost=supplier_cost, ship_cost=ship_cost,
        fee_rate=fee_rate, landed_cost=landed_cost, fee=fee, gross_profit=gross_profit,
        gross_margin=gross_margin, breakeven_roas=breakeven_roas, max_cac=max_cac,
        return_rate=return_rate, profit_after_returns=profit_after_returns,
    )
