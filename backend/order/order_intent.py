"""OrderIntent — 주문 의도 모델

OrderIntent는 RiskDecision 승인 후 생성되는 주문 의도다.
실제 주문은 아니며, LiveOrderGate를 통과해야 OrderSubmitter로 전달된다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

from order.order_types import OrderSide, OrderType


@dataclass(frozen=True)
class OrderIntent:
    order_intent_id: str
    risk_decision_id: str
    signal_id: str
    correlation_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: int
    estimated_amount: int
    source_strategy: str
    source_endpoints: tuple[str, ...] = ()
    live_trading_enabled_snapshot: bool = False
    approved_by_risk: bool = True
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
