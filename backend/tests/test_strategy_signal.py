"""Tests for StrategySignal model"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from strategy.strategy_types import StrategyType
from strategy.signal import StrategySignal


def _make_signal(side="BUY", **overrides) -> StrategySignal:
    defaults = {
        "signal_id": "sig_001",
        "correlation_id": "corr_abc",
        "symbol": "005930",
        "side": side,
        "strategy_type": StrategyType.RAPID_SURGE_SCALPING,
        "confidence": 0.85,
        "source_quant_id": "eval_abc123",
        "scanner_type": "RAPID_SURGE",
        "market_regime": "BULL",
        "expected_entry_price": 75000,
        "suggested_stop_loss_rate": 0.02,
        "suggested_take_profit_rate": 0.03,
        "suggested_time_exit_minutes": 15,
        "evidence": ("strong_momentum", "high_volume"),
        "source_endpoints": ("kis/quote",),
    }
    defaults.update(overrides)
    return StrategySignal(**defaults)


class TestStrategySignal:
    def test_minimal_signal(self):
        sig = StrategySignal(
            signal_id="sig_001",
            correlation_id="corr_abc",
            symbol="005930",
            side="BUY",
            strategy_type=StrategyType.RAPID_SURGE_SCALPING,
            source_quant_id="eval_001",
            scanner_type="RAPID_SURGE",
            market_regime="BULL",
        )
        assert sig.signal_id == "sig_001"
        assert sig.side == "BUY"
        assert sig.confidence == 0.0
        assert sig.evidence == ()

    def test_full_signal(self):
        sig = _make_signal()
        assert sig.symbol == "005930"
        assert sig.confidence == 0.85
        assert sig.expected_entry_price == 75000
        assert sig.suggested_stop_loss_rate == 0.02
        assert sig.suggested_time_exit_minutes == 15
        assert "strong_momentum" in sig.evidence

    def test_buy_signal(self):
        sig = _make_signal(side="BUY")
        assert sig.side == "BUY"

    def test_sell_signal(self):
        sig = _make_signal(side="SELL")
        assert sig.side == "SELL"

    def test_signal_is_frozen(self):
        sig = _make_signal()
        with pytest.raises(Exception):
            sig.confidence = 1.0  # type: ignore

    def test_created_at_defaults_to_now(self):
        sig = _make_signal()
        now = datetime.now(timezone.utc)
        diff = now - sig.created_at
        assert diff.seconds < 10

    def test_signal_has_no_order_fields(self):
        """StrategySignal은 주문 객체가 아니다"""
        sig = _make_signal()
        sig_dict = sig.__dict__
        forbidden = {"execute_orders", "place_order", "order_manager",
                     "quantity", "stop_loss_price", "take_profit_price",
                     "order_id"}
        for field in forbidden:
            assert field not in sig_dict

    def test_data_quality_warnings_default(self):
        sig = _make_signal()
        assert sig.data_quality_warnings == ()

    def test_all_5_strategy_types_work(self):
        for stype in StrategyType:
            sig = _make_signal(strategy_type=stype)
            assert sig.strategy_type == stype
