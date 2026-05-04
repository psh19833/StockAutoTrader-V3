"""LiveOrderGate — 실전 주문 전 최종 차단문

RiskDecision APPROVED 이후에도 최종 게이트를 통과해야 주문 가능.
LIVE_TRADING_ENABLED=false가 기본값 — 실전 주문 차단.
"""
from __future__ import annotations
from dataclasses import dataclass

from risk.risk_decision import RiskDecision
from order.order_result import OrderSubmitResult, OrderResultStatus
from session.session_state import TradingSessionState


@dataclass(frozen=True)
class LiveOrderGate:
    live_trading_enabled: bool = False
    emergency_stop: bool = False
    session_state: TradingSessionState = TradingSessionState.CLOSED_HOLIDAY
    allow_new_buy: bool = False
    max_order_amount: int = 10_000_000

    def check(self, risk_decision: RiskDecision,
              estimated_amount: int = 0) -> OrderSubmitResult:
        order_id = risk_decision.risk_decision_id

        # 1. RiskDecision allowed?
        if not risk_decision.allowed:
            return OrderSubmitResult(
                order_intent_id=order_id,
                status=OrderResultStatus.ORDER_REJECTED_BY_GATE,
                allowed=False,
                message="RiskDecision not allowed",
            )

        # 2. LIVE_TRADING_ENABLED?
        if not self.live_trading_enabled:
            return OrderSubmitResult(
                order_intent_id=order_id,
                status=OrderResultStatus.ORDER_REJECTED_BY_GATE,
                allowed=False,
                message="Live trading disabled",
            )

        # 3. Emergency Stop?
        if self.emergency_stop:
            return OrderSubmitResult(
                order_intent_id=order_id,
                status=OrderResultStatus.ORDER_REJECTED_BY_GATE,
                allowed=False,
                message="Emergency stop active",
            )

        # 4. Session State — only REGULAR_MARKET allowed
        if self.session_state != TradingSessionState.REGULAR_MARKET:
            return OrderSubmitResult(
                order_intent_id=order_id,
                status=OrderResultStatus.ORDER_REJECTED_BY_GATE,
                allowed=False,
                message=f"Session not regular market: {self.session_state.value}",
            )

        # 5. Market Regime allow_new_buy?
        if not self.allow_new_buy:
            return OrderSubmitResult(
                order_intent_id=order_id,
                status=OrderResultStatus.ORDER_REJECTED_BY_GATE,
                allowed=False,
                message="Market regime blocks new buys",
            )

        # 6. Amount within limit?
        if estimated_amount > self.max_order_amount:
            return OrderSubmitResult(
                order_intent_id=order_id,
                status=OrderResultStatus.ORDER_REJECTED_BY_GATE,
                allowed=False,
                message=f"Amount {estimated_amount} exceeds max {self.max_order_amount}",
            )

        # All checks passed
        return OrderSubmitResult(
            order_intent_id=order_id,
            status=OrderResultStatus.ORDER_SUBMITTED,
            allowed=True,
            message="Order submitted",
        )
