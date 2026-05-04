"""Tests for Strategy Audit Events"""
from __future__ import annotations

from strategy.strategy_types import StrategyType
from strategy.signal import StrategySignal
from strategy.strategy_audit import build_strategy_signal_event


def _make_signal(**overrides) -> StrategySignal:
    defaults = {
        "signal_id": "sig_001",
        "correlation_id": "corr_abc",
        "symbol": "005930",
        "side": "BUY",
        "strategy_type": StrategyType.RAPID_SURGE_SCALPING,
        "confidence": 0.85,
        "source_quant_id": "eval_abc123",
        "scanner_type": "RAPID_SURGE",
        "market_regime": "BULL",
        "evidence": ("strong_momentum",),
        "source_endpoints": ("kis/quote",),
    }
    defaults.update(overrides)
    return StrategySignal(**defaults)


class TestBuildStrategySignalEvent:
    def test_event_type(self):
        event = build_strategy_signal_event(_make_signal())
        assert event.event_type == "STRATEGY_SIGNAL_CREATED"

    def test_signal_id_in_payload(self):
        event = build_strategy_signal_event(_make_signal())
        assert event.payload["signal_id"] == "sig_001"

    def test_side_in_payload(self):
        event = build_strategy_signal_event(_make_signal(side="BUY"))
        assert event.payload["side"] == "BUY"

    def test_confidence_in_payload(self):
        event = build_strategy_signal_event(_make_signal(confidence=0.92))
        assert event.payload["confidence"] == 0.92

    def test_evidence_in_payload(self):
        event = build_strategy_signal_event(_make_signal(evidence=("test",)))
        assert "test" in event.payload["evidence"]

    def test_no_order_fields(self):
        event = build_strategy_signal_event(_make_signal())
        payload_str = str(event.payload)
        for field in ["execute_orders", "order_manager",
                       "quantity", "stop_loss_price"]:
            assert field not in payload_str

    def test_no_secret_leak(self):
        event = build_strategy_signal_event(_make_signal())
        payload_str = str(event.payload)
        for secret in ["app_key", "api_key", "token",
                        "account_no", "chat_id"]:
            assert secret not in payload_str
