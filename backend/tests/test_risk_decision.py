"""Tests for RiskDecision model"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from risk.risk_types import RiskDecisionStatus, RiskRejectReason
from risk.risk_decision import RiskDecision


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


class TestRiskDecision:
    def test_approved_decision(self):
        rd = _make_decision(allowed=True)
        assert rd.allowed is True
        assert rd.status == RiskDecisionStatus.APPROVED

    def test_rejected_decision(self):
        rd = _make_decision(allowed=False)
        assert rd.allowed is False
        assert rd.status == RiskDecisionStatus.REJECTED

    def test_blocked_decision(self):
        rd = _make_decision(allowed=False, status=RiskDecisionStatus.BLOCKED)
        assert rd.allowed is False
        assert rd.status == RiskDecisionStatus.BLOCKED

    def test_checked_items_present(self):
        rd = _make_decision()
        assert "market_regime_check" in rd.checked_items

    def test_failed_items_present_on_reject(self):
        rd = _make_decision(allowed=False)
        assert len(rd.failed_items) > 0

    def test_decision_is_frozen(self):
        rd = _make_decision()
        with pytest.raises(Exception):
            rd.allowed = True  # type: ignore

    def test_created_at_default(self):
        rd = _make_decision()
        now = datetime.now(timezone.utc)
        diff = now - rd.created_at
        assert diff.seconds < 10

    def test_reason_code_set(self):
        rd = _make_decision(allowed=False,
                            reason_code=RiskRejectReason.SESSION_BLOCKED.value)
        assert rd.reason_code == RiskRejectReason.SESSION_BLOCKED.value

    def test_no_order_fields(self):
        rd = _make_decision()
        rd_dict = rd.__dict__
        for field in ["execute_orders", "order_manager", "quantity"]:
            assert field not in rd_dict
