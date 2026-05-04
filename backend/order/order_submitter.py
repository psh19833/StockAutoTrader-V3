"""OrderSubmitter — 주문 제출 인터페이스

SafeStubSubmitter는 테스트 전용 TestDouble.
실제 KIS 주문 호출은 구현하지 않는다.
모든 실패는 예외가 아닌 OrderSubmitResult로 반환한다.
"""
from __future__ import annotations
from dataclasses import dataclass

from order.order_intent import OrderIntent
from order.order_result import OrderSubmitResult, OrderResultStatus


class SafeStubSubmitter:
    """테스트 전용 Safe Stub Submitter — 실제 HTTP 호출 없음"""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def submit(self, intent: OrderIntent) -> OrderSubmitResult:
        if self.should_fail:
            return OrderSubmitResult(
                order_intent_id=intent.order_intent_id,
                status=OrderResultStatus.ORDER_FAILED,
                allowed=False,
                message="Submitter configured to fail (test)",
            )
        return OrderSubmitResult(
            order_intent_id=intent.order_intent_id,
            status=OrderResultStatus.ORDER_SUBMITTED,
            allowed=True,
            message="Order submitted (stub)",
        )
