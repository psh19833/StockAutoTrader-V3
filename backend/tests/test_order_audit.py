"""Tests for Order Audit Events"""
from __future__ import annotations

from order.order_types import OrderSide, OrderType
from order.order_intent import OrderIntent
from order.order_audit import build_order_intent_event


def _make_intent(**overrides) -> OrderIntent:
    defaults = {
        "order_intent_id": "oi_001", "risk_decision_id": "rd_001",
        "signal_id": "sig_001", "correlation_id": "corr_abc",
        "symbol": "005930", "side": OrderSide.BUY,
        "order_type": OrderType.MARKET, "quantity": 10, "price": 0,
        "estimated_amount": 750000, "source_strategy": "RAPID_SURGE_SCALPING",
        "source_endpoints": ("kis/quote",),
        "live_trading_enabled_snapshot": False, "approved_by_risk": True,
    }
    defaults.update(overrides)
    return OrderIntent(**defaults)


class TestOrderAudit:
    def test_event_type(self):
        event = build_order_intent_event(_make_intent())
        assert event.event_type == "ORDER_INTENT_APPROVED"

    def test_payload_has_symbol(self):
        event = build_order_intent_event(_make_intent())
        assert event.payload["symbol"] == "005930"

    def test_payload_has_side(self):
        event = build_order_intent_event(_make_intent(side=OrderSide.BUY))
        assert event.payload["side"] == "BUY"

    def test_no_secret_leak(self):
        event = build_order_intent_event(_make_intent())
        payload_str = str(event.payload)
        for secret in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert secret not in payload_str

    def test_no_execute_order_field(self):
        event = build_order_intent_event(_make_intent())
        for field in ["execute_orders", "place_order", "broker"]:
            assert field not in str(event.payload)
