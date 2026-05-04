"""Tests for OrderIntent — 주문 의도 모델"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from order.order_types import OrderSide, OrderType
from order.order_intent import OrderIntent


def _make_intent(**overrides) -> OrderIntent:
    defaults = {
        "order_intent_id": "oi_001",
        "risk_decision_id": "rd_001",
        "signal_id": "sig_001",
        "correlation_id": "corr_abc",
        "symbol": "005930",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": 10,
        "price": 0,
        "estimated_amount": 750000,
        "source_strategy": "RAPID_SURGE_SCALPING",
        "source_endpoints": ("kis/quote",),
        "live_trading_enabled_snapshot": False,
        "approved_by_risk": True,
    }
    defaults.update(overrides)
    return OrderIntent(**defaults)


class TestOrderIntent:
    def test_create_buy_intent(self):
        oi = _make_intent(side=OrderSide.BUY)
        assert oi.side == OrderSide.BUY
        assert oi.symbol == "005930"

    def test_create_sell_intent(self):
        oi = _make_intent(side=OrderSide.SELL)
        assert oi.side == OrderSide.SELL

    def test_intent_is_frozen(self):
        oi = _make_intent()
        with pytest.raises(Exception):
            oi.quantity = 20  # type: ignore

    def test_default_live_trading_snapshot_false(self):
        oi = _make_intent(live_trading_enabled_snapshot=False)
        assert oi.live_trading_enabled_snapshot is False

    def test_created_at_default(self):
        oi = _make_intent()
        now = datetime.now(timezone.utc)
        diff = now - oi.created_at
        assert diff.seconds < 10

    def test_risk_decision_required(self):
        oi = _make_intent(risk_decision_id="rd_001")
        assert oi.risk_decision_id == "rd_001"

    def test_signal_id_linked(self):
        oi = _make_intent(signal_id="sig_001")
        assert oi.signal_id == "sig_001"

    def test_no_broker_fields(self):
        oi = _make_intent()
        rd = oi.__dict__
        for field in ["broker", "execute_orders", "place_order",
                       "api_key", "token"]:
            assert field not in rd
