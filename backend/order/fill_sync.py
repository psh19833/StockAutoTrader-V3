"""Fill Sync — 체결 동기화

주문 성공 != 체결 성공
체결은 KIS 체결조회/체결통보 기준으로만 확정한다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class FillConfirmed:
    fill_id: str
    order_intent_id: str
    symbol: str
    side: str
    filled_qty: int
    filled_price: int
    remaining_qty: int = 0
    confirmed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def partial_fill(order_intent_id: str, symbol: str, side: str,
                 filled_qty: int, filled_price: int,
                 remaining_qty: int) -> FillConfirmed:
    return FillConfirmed(
        fill_id=f"fill_{order_intent_id}",
        order_intent_id=order_intent_id,
        symbol=symbol, side=side,
        filled_qty=filled_qty, filled_price=filled_price,
        remaining_qty=remaining_qty,
    )
