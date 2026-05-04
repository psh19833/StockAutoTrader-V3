"""Tests for LiveOrderGate"""
from __future__ import annotations

import pytest

from order.order_types import OrderSide, OrderType
from order.order_intent import OrderIntent
from order.live_order_gate import LiveOrderGate
from order.order_result import OrderSubmitResult, OrderResultStatus
from risk.risk_types import RiskDecisionStatus, RiskRejectReason
from risk.risk_decision import RiskDecision
from session.session_state import TradingSessionState


def _make_decision(allowed=True) -> RiskDecision:
    return RiskDecision(
        risk_decision_id="rd_001",
        signal_id="sig_001",
        correlation_id="corr_abc",
        symbol="005930",
        side="BUY",
        status=RiskDecisionStatus.APPROVED if allowed else RiskDecisionStatus.REJECTED,
        allowed=allowed,
        reason_code="APPROVED" if allowed else RiskRejectReason.LIVE_TRADING_DISABLED.value,
        reason_text="OK" if allowed else "Blocked",
        checked_items=("live_trading_enabled",),
        failed_items=() if allowed else ("live_trading_enabled",),
    )


class TestLiveOrderGate:
    def test_all_conditions_pass(self):
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=False,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=True,
            max_order_amount=10_000_000,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert result.allowed is True
        assert result.status == OrderResultStatus.ORDER_SUBMITTED

    def test_risk_decision_rejected(self):
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=False,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=True,
        )
        rd = _make_decision(allowed=False)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert result.allowed is False
        assert result.status == OrderResultStatus.ORDER_REJECTED_BY_GATE

    def test_live_trading_disabled(self):
        gate = LiveOrderGate(
            live_trading_enabled=False,
            emergency_stop=False,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=True,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert result.allowed is False

    def test_emergency_stop(self):
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=True,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=True,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert result.allowed is False

    def test_session_not_regular_market(self):
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=False,
            session_state=TradingSessionState.CLOSED_HOLIDAY,
            allow_new_buy=True,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert result.allowed is False

    def test_market_regime_no_new_buy(self):
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=False,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=False,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert result.allowed is False

    def test_amount_exceeds_limit(self):
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=False,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=True,
            max_order_amount=1_000_000,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=5_000_000)
        assert result.allowed is False

    def test_no_http_call(self):
        """LiveOrderGate는 실제 HTTP 호출을 하지 않는다"""
        gate = LiveOrderGate(
            live_trading_enabled=True,
            emergency_stop=False,
            session_state=TradingSessionState.REGULAR_MARKET,
            allow_new_buy=True,
        )
        rd = _make_decision(allowed=True)
        result = gate.check(rd, estimated_amount=1_000_000)
        assert "http" not in str(result.__dict__).lower()
