"""Tests for Risk Audit Events"""
from __future__ import annotations

from risk.risk_types import RiskDecisionStatus, RiskRejectReason
from risk.risk_decision import RiskDecision
from risk.risk_audit import build_risk_audit_event


def _make_decision(allowed=True, **overrides) -> RiskDecision:
    defaults = {
        "risk_decision_id": "rd_001",
        "signal_id": "sig_001",
        "correlation_id": "corr_abc",
        "symbol": "005930",
        "side": "BUY",
        "status": RiskDecisionStatus.APPROVED if allowed else RiskDecisionStatus.REJECTED,
        "allowed": allowed,
        "reason_code": "APPROVED" if allowed else RiskRejectReason.MARKET_REGIME_BLOCKED.value,
        "reason_text": "All checks passed" if allowed else "Market regime blocks new buys",
        "checked_items": ("market_regime_check", "session_check"),
        "failed_items": () if allowed else ("market_regime_check",),
        "market_regime": "BULL",
        "session_state": "REGULAR_MARKET",
        "requested_amount": 1_000_000,
    }
    defaults.update(overrides)
    return RiskDecision(**defaults)


class TestBuildRiskAuditEvent:
    def test_approved_event_type(self):
        rd = _make_decision(allowed=True)
        event = build_risk_audit_event(rd)
        assert event.event_type == "RISK_APPROVED"

    def test_rejected_event_type(self):
        rd = _make_decision(allowed=False)
        event = build_risk_audit_event(rd)
        assert event.event_type == "RISK_REJECTED"

    def test_payload_has_decision_id(self):
        event = build_risk_audit_event(_make_decision())
        assert event.payload["risk_decision_id"] == "rd_001"

    def test_payload_has_reason_code(self):
        rd = _make_decision(allowed=False)
        event = build_risk_audit_event(rd)
        assert "reason_code" in event.payload

    def test_payload_has_checked_items(self):
        event = build_risk_audit_event(_make_decision())
        assert "checked_items" in event.payload

    def test_payload_has_failed_items(self):
        rd = _make_decision(allowed=False)
        event = build_risk_audit_event(rd)
        assert "failed_items" in event.payload

    def test_no_secret_leak(self):
        event = build_risk_audit_event(_make_decision())
        payload_str = str(event.payload)
        for secret in ["app_key", "api_key", "token",
                        "account_no", "chat_id"]:
            assert secret not in payload_str

    def test_no_order_execution(self):
        event = build_risk_audit_event(_make_decision())
        payload_str = str(event.payload)
        for field in ["execute_orders", "order_submitted", "place_order"]:
            assert field not in payload_str
