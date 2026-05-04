"""Tests for OrderResult, OrderSubmitter, FillSync"""
from __future__ import annotations

from order.order_types import OrderSide, OrderType
from order.order_intent import OrderIntent
from order.order_result import OrderSubmitResult, OrderResultStatus
from order.order_submitter import SafeStubSubmitter
from order.fill_sync import FillConfirmed, partial_fill


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


class TestOrderResultStatus:
    def test_statuses(self):
        assert OrderResultStatus.ORDER_SUBMITTED.value == "ORDER_SUBMITTED"
        assert OrderResultStatus.ORDER_FAILED.value == "ORDER_FAILED"
        assert OrderResultStatus.ORDER_REJECTED_BY_GATE.value == "ORDER_REJECTED_BY_GATE"

    def test_all_values_unique(self):
        values = [s.value for s in OrderResultStatus]
        assert len(values) == len(set(values))


class TestSafeStubSubmitter:
    def test_submit_returns_result(self):
        submitter = SafeStubSubmitter()
        intent = _make_intent()
        result = submitter.submit(intent)
        assert isinstance(result, OrderSubmitResult)
        assert result.order_intent_id == intent.order_intent_id

    def test_submit_no_http(self):
        submitter = SafeStubSubmitter()
        result = submitter.submit(_make_intent())
        assert result.status == OrderResultStatus.ORDER_SUBMITTED

    def test_failure_returns_result_not_exception(self):
        submitter = SafeStubSubmitter(should_fail=True)
        intent = _make_intent()
        result = submitter.submit(intent)
        assert result.status == OrderResultStatus.ORDER_FAILED
        assert result.allowed is False


class TestFillConfirmed:
    def test_create_fill(self):
        fill = FillConfirmed(
            fill_id="fill_001", order_intent_id="oi_001",
            symbol="005930", side="BUY", filled_qty=10,
            filled_price=75000, remaining_qty=0,
        )
        assert fill.symbol == "005930"
        assert fill.filled_qty == 10
        assert fill.remaining_qty == 0

    def test_partial_fill(self):
        fill = FillConfirmed(
            fill_id="fill_002", order_intent_id="oi_002",
            symbol="000660", side="BUY", filled_qty=5,
            filled_price=150000, remaining_qty=5,
        )
        assert fill.remaining_qty > 0
        assert fill.filled_qty + fill.remaining_qty == 10  # total

    def test_fill_frozen(self):
        import pytest
        fill = FillConfirmed(
            fill_id="fill_003", order_intent_id="oi_003",
            symbol="035420", side="SELL", filled_qty=10,
            filled_price=95000, remaining_qty=0,
        )
        with pytest.raises(Exception):
            fill.filled_qty = 20  # type: ignore

    def test_order_success_not_fill_success(self):
        """주문 제출 성공 ≠ 체결 성공"""
        intent = _make_intent()
        result = SafeStubSubmitter().submit(intent)
        # OrderSubmitResult is NOT a FillConfirmed
        assert not isinstance(result, FillConfirmed)
        assert not hasattr(result, "filled_qty")
        assert not hasattr(result, "filled_price")


def test_partial_fill_helper():
    fill = partial_fill(
        order_intent_id="oi_001", symbol="005930", side="BUY",
        filled_qty=3, filled_price=75000, remaining_qty=7,
    )
    assert fill.filled_qty == 3
    assert fill.remaining_qty == 7
