"""PositionSnapshot — 보유 포지션 스냅샷"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    name: str
    quantity: int
    avg_buy_price: int
    current_price: int
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
