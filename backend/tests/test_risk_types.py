"""Tests for Risk Types — RiskDecisionStatus, RiskRejectReason"""
from __future__ import annotations

from risk.risk_types import RiskDecisionStatus, RiskRejectReason


class TestRiskDecisionStatus:
    def test_has_3_statuses(self):
        assert len(RiskDecisionStatus) == 3

    def test_approved(self):
        assert RiskDecisionStatus.APPROVED.value == "APPROVED"

    def test_rejected(self):
        assert RiskDecisionStatus.REJECTED.value == "REJECTED"

    def test_blocked(self):
        assert RiskDecisionStatus.BLOCKED.value == "BLOCKED"


class TestRiskRejectReason:
    def test_has_all_reasons(self):
        expected = {
            "MARKET_REGIME_BLOCKED", "SESSION_BLOCKED",
            "QUANT_REJECTED", "DUPLICATE_ORDER_BLOCKED",
            "REENTRY_BLOCKED", "DAILY_LOSS_LIMIT_BLOCKED",
            "SYMBOL_EXPOSURE_BLOCKED", "POSITION_LIMIT_BLOCKED",
            "STALE_DATA_BLOCKED", "DATA_QUALITY_BLOCKED",
            "EMERGENCY_STOP_BLOCKED", "LIVE_TRADING_DISABLED",
            "SELL_BLOCKED_NO_POSITION", "BUY_BLOCKED_NON_POSITIVE_AMOUNT",
            "BUY_BLOCKED_LOW_CONFIDENCE", "BUY_BLOCKED_MISSING_QUANT_SOURCE",
            "UNKNOWN",
        }
        actual = {r.value for r in RiskRejectReason}
        assert expected == actual

    def test_live_trading_disabled(self):
        assert RiskRejectReason.LIVE_TRADING_DISABLED.value == "LIVE_TRADING_DISABLED"

    def test_market_regime_blocked(self):
        assert RiskRejectReason.MARKET_REGIME_BLOCKED.value == "MARKET_REGIME_BLOCKED"

    def test_emergency_stop_blocked(self):
        assert RiskRejectReason.EMERGENCY_STOP_BLOCKED.value == "EMERGENCY_STOP_BLOCKED"
