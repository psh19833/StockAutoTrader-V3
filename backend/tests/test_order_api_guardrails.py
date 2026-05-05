from __future__ import annotations

from kis.order_api import OrderSubmitResult, submit_cash_order
from safety.live_order_safety_gate import SafetyGateResult


class FakeSubmitter:
    def submit_cash_order(self, payload: dict, tr_id: str) -> OrderSubmitResult:
        # Explicitly fake: production code must inject a real submitter.
        return OrderSubmitResult(
            success=True,
            order_number="FAKE-ORDER-123",
            message="fake submitter used",
        )


def test_live_false_blocked():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        live_trading_enabled=False,
        safety_gate_approved=True,
        safety_gate_result=SafetyGateResult(passed=True, block_reasons=[]),
        submitter=FakeSubmitter(),
    )
    assert r.success is False
    assert r.error_type == "LIVE_TRADING_DISABLED"


def test_safety_gate_false_blocked():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        live_trading_enabled=True,
        safety_gate_approved=False,
        safety_gate_result=SafetyGateResult(passed=False, block_reasons=["risk_not_approved"]),
        submitter=FakeSubmitter(),
    )
    assert r.success is False
    assert r.error_type == "SAFETY_GATE_NOT_APPROVED"


def test_safety_gate_chain_required_even_if_bool_true():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        live_trading_enabled=True,
        safety_gate_approved=True,
        safety_gate_result=None,
        submitter=FakeSubmitter(),
    )
    assert r.success is False
    assert r.error_type == "SAFETY_GATE_CHAIN_REQUIRED"


def test_live_true_safety_true_but_no_submitter_is_not_success():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        live_trading_enabled=True,
        safety_gate_approved=True,
        safety_gate_result=SafetyGateResult(passed=True, block_reasons=[]),
        submitter=None,
    )
    assert r.success is False
    assert r.error_type == "ORDER_SUBMITTER_NOT_CONFIGURED"


def test_mock_order_number_not_returned_from_core_function():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        live_trading_enabled=True,
        safety_gate_approved=True,
        safety_gate_result=SafetyGateResult(passed=True, block_reasons=[]),
        submitter=None,
    )
    assert "MOCK-ORDER" not in (r.order_number or "")


def test_fake_submitter_can_return_fake_result_only_when_explicitly_injected():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        live_trading_enabled=True,
        safety_gate_approved=True,
        safety_gate_result=SafetyGateResult(passed=True, block_reasons=[]),
        submitter=FakeSubmitter(),
    )
    assert r.success is True
    assert r.order_number.startswith("FAKE-")
