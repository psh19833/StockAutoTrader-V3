"""Order Result — 주문 제출 결과

ORDER_SUBMITTED != FILL_CONFIRMED
주문 제출 성공이 체결 성공을 의미하지 않는다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class OrderResultStatus(str, Enum):
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FAILED = "ORDER_FAILED"
    ORDER_REJECTED_BY_GATE = "ORDER_REJECTED_BY_GATE"
    ORDER_CANCEL_REQUESTED = "ORDER_CANCEL_REQUESTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"


@dataclass(frozen=True)
class OrderSubmitResult:
    order_intent_id: str
    status: OrderResultStatus
    allowed: bool
    message: str = ""
    submitted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
