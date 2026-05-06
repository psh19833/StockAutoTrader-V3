from __future__ import annotations

import main
from kis.order_api import submit_cash_order, OrderSubmitResult
from safety.live_order_safety_gate import SafetyGateResult


def _ok_gate() -> SafetyGateResult:
    return SafetyGateResult(passed=True, checks=[], block_reasons=[])


def test_runtime_start_live_endpoint_requires_confirm():
    r = __import__("asyncio").run(main.runtime_start_live({}))
    assert r["started"] is False
    assert r["reason"] == "LIVE_CONFIRM_REQUIRED"


def test_order_blocked_without_safety_gate_result():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        price=100,
        account_no="44413716-01",
        live_trading_enabled=True,
        risk_decision_approved=True,
        correlation_id="cid-1",
        submitter=None,
    )
    assert r.success is False
    assert r.error_type == "SAFETY_GATE_CHAIN_REQUIRED"


def test_order_blocked_when_risk_rejected():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        price=100,
        account_no="44413716-01",
        live_trading_enabled=True,
        risk_decision_approved=False,
        safety_gate_result=_ok_gate(),
        safety_gate_approved=True,
        correlation_id="cid-1",
        strict_validation=True,
        submitter=None,
    )
    assert r.success is False
    assert r.error_type == "RISK_NOT_APPROVED"


def test_order_blocked_without_correlation_id():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        price=100,
        account_no="44413716-01",
        live_trading_enabled=True,
        risk_decision_approved=True,
        safety_gate_result=_ok_gate(),
        safety_gate_approved=True,
        correlation_id="",
        strict_validation=True,
        submitter=None,
    )
    assert r.success is False
    assert r.error_type == "CORRELATION_ID_REQUIRED"


class _MockSubmitter:
    def submit_cash_order(self, payload: dict, tr_id: str) -> OrderSubmitResult:
        return OrderSubmitResult(True, order_number="A123", message="ORDER_SUBMITTED")


def test_order_submitted_with_mock_submitter_success():
    r = submit_cash_order(
        symbol="005930",
        side="BUY",
        qty=1,
        price=100,
        account_no="44413716-01",
        live_trading_enabled=True,
        risk_decision_approved=True,
        safety_gate_result=_ok_gate(),
        safety_gate_approved=True,
        correlation_id="cid-1",
        submitter=_MockSubmitter(),
    )
    assert r.success is True
    assert r.message == "ORDER_SUBMITTED"
