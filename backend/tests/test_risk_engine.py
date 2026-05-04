"""Tests for Risk Engine — gate checks and evaluation"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from risk.risk_types import RiskDecisionStatus, RiskRejectReason
from risk.risk_decision import RiskDecision
from risk.risk_config import RiskLimits
from risk.risk_context import RiskContext
from risk.risk_engine import evaluate_risk, check_live_trading_enabled, check_emergency_stop
from strategy.strategy_types import StrategyType
from strategy.signal import StrategySignal
from market_regime.regime_state import MarketRegime
from market_regime.regime_score import MarketRegimeScore
from market_regime.regime_result import MarketRegimeResult
from session.session_state import TradingSessionState


def _make_regime(regime=MarketRegime.BULL, allow_new_buy=True):
    score = MarketRegimeScore(
        index_trend_score=15.0, market_breadth_score=10.0,
        market_momentum_score=10.0, volatility_risk_score=10.0,
        trading_value_score=8.0, sector_strength_score=8.0,
        foreign_institution_flow_score=4.0, market_risk_penalty=0.0,
    )
    return MarketRegimeResult(
        regime=regime, score=score, total_score=score.total_score,
        candidate_score_adjustment=5.0, allow_new_buy=allow_new_buy,
        min_candidate_score_required=50.0, source_endpoints=("kis/index",),
    )


def _make_signal(side="BUY", **overrides) -> StrategySignal:
    defaults = {
        "signal_id": "sig_001",
        "correlation_id": "corr_abc",
        "symbol": "005930",
        "side": side,
        "strategy_type": StrategyType.RAPID_SURGE_SCALPING,
        "confidence": 0.85,
        "source_quant_id": "eval_001",
        "scanner_type": "RAPID_SURGE",
        "market_regime": "BULL",
        "source_endpoints": ("kis/quote",),
    }
    defaults.update(overrides)
    return StrategySignal(**defaults)


def _make_context(
    regime=None, session_state=None, live_trading=True,
    emergency_stop=False, daily_loss=0, daily_loss_limit=1_000_000,
    current_positions=None, pending_orders=None,
):
    if regime is None:
        regime = _make_regime()
    if session_state is None:
        session_state = TradingSessionState.REGULAR_MARKET
    return RiskContext(
        market_regime_result=regime,
        session_state=session_state,
        emergency_stop=emergency_stop,
        live_trading_enabled=live_trading,
        current_positions=current_positions or frozenset(),
        pending_orders=pending_orders or frozenset(),
        today_realized_pnl=daily_loss,
        daily_loss_limit=daily_loss_limit,
        data_quality_warnings=(),
    )


class TestCheckLiveTradingEnabled:
    def test_disabled_blocks(self):
        result = check_live_trading_enabled(False)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.LIVE_TRADING_DISABLED

    def test_enabled_allows(self):
        result = check_live_trading_enabled(True)
        assert result.allowed is True


class TestCheckEmergencyStop:
    def test_active_blocks(self):
        result = check_emergency_stop(True)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.EMERGENCY_STOP_BLOCKED

    def test_inactive_allows(self):
        result = check_emergency_stop(False)
        assert result.allowed is True


class TestEvaluateRisk:
    def test_all_checks_pass(self):
        signal = _make_signal()
        context = _make_context()
        result = evaluate_risk(signal, context)
        assert result.allowed is True
        assert result.status == RiskDecisionStatus.APPROVED

    def test_live_trading_disabled_blocks(self):
        signal = _make_signal()
        context = _make_context(live_trading=False)
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.LIVE_TRADING_DISABLED.value

    def test_emergency_stop_blocks(self):
        signal = _make_signal()
        context = _make_context(emergency_stop=True)
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.EMERGENCY_STOP_BLOCKED.value

    def test_market_regime_unknown_blocks(self):
        signal = _make_signal()
        context = _make_context(
            regime=_make_regime(MarketRegime.UNKNOWN, allow_new_buy=False)
        )
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.MARKET_REGIME_BLOCKED.value

    def test_market_regime_bear_blocks(self):
        signal = _make_signal()
        context = _make_context(
            regime=_make_regime(MarketRegime.BEAR, allow_new_buy=False)
        )
        result = evaluate_risk(signal, context)
        assert result.allowed is False

    def test_session_unknown_blocks(self):
        signal = _make_signal()
        context = _make_context(
            session_state=TradingSessionState.SESSION_STATE_UNKNOWN
        )
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.SESSION_BLOCKED.value

    def test_closed_holiday_blocks(self):
        signal = _make_signal()
        context = _make_context(
            session_state=TradingSessionState.CLOSED_HOLIDAY
        )
        result = evaluate_risk(signal, context)
        assert result.allowed is False

    def test_late_market_blocks_new_buy(self):
        signal = _make_signal(side="BUY")
        context = _make_context(
            session_state=TradingSessionState.LATE_MARKET
        )
        result = evaluate_risk(signal, context)
        assert result.allowed is False

    def test_duplicate_pending_order_blocks(self):
        signal = _make_signal(symbol="005930")
        context = _make_context(pending_orders=frozenset({"005930"}))
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.DUPLICATE_ORDER_BLOCKED.value

    def test_duplicate_position_blocks(self):
        signal = _make_signal(symbol="005930")
        context = _make_context(current_positions=frozenset({"005930"}))
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.SYMBOL_EXPOSURE_BLOCKED.value

    def test_daily_loss_limit_exceeded(self):
        signal = _make_signal()
        context = _make_context(daily_loss=-1_500_000, daily_loss_limit=1_000_000)
        result = evaluate_risk(signal, context)
        assert result.allowed is False
        assert result.reason_code == RiskRejectReason.DAILY_LOSS_LIMIT_BLOCKED.value

    def test_sell_signal_always_allowed_session_checks(self):
        """SELL 청산은 세션 체크에서 더 관대"""
        signal = _make_signal(side="SELL",
                              strategy_type=StrategyType.FAST_EXIT)
        context = _make_context()
        result = evaluate_risk(signal, context)
        assert result.allowed is True

    def test_result_includes_checked_items(self):
        signal = _make_signal()
        context = _make_context()
        result = evaluate_risk(signal, context)
        assert len(result.checked_items) > 0
        assert "live_trading_enabled" in result.checked_items

    def test_rejected_includes_failed_items(self):
        signal = _make_signal()
        context = _make_context(live_trading=False)
        result = evaluate_risk(signal, context)
        assert len(result.failed_items) > 0
        assert "live_trading_enabled" in result.failed_items

    def test_risk_decision_includes_session_state(self):
        signal = _make_signal()
        context = _make_context(session_state=TradingSessionState.REGULAR_MARKET)
        result = evaluate_risk(signal, context)
        assert result.session_state == TradingSessionState.REGULAR_MARKET.value

    def test_risk_decision_includes_market_regime(self):
        signal = _make_signal(market_regime="BULL")
        context = _make_context()
        result = evaluate_risk(signal, context)
        assert result.market_regime == "BULL"

    def test_no_order_execution(self):
        """RiskDecision은 실제 주문을 만들지 않는다"""
        signal = _make_signal()
        context = _make_context()
        result = evaluate_risk(signal, context)
        rd_dict = result.__dict__
        for field in ["execute_orders", "order_submitted", "broker",
                       "place_order"]:
            assert field not in rd_dict


class TestRiskLimitsDefaults:
    def test_default_limits(self):
        limits = RiskLimits()
        assert limits.max_position_count == 5
        assert limits.max_amount_per_symbol == 10_000_000
        assert limits.max_daily_loss_amount == 1_000_000
        assert limits.max_daily_loss_rate == 0.03
        assert limits.reentry_block_minutes == 30
        assert limits.min_candidate_score_for_buy == 50.0

    def test_custom_limits(self):
        limits = RiskLimits(max_position_count=3, max_amount_per_symbol=5_000_000)
        assert limits.max_position_count == 3
        assert limits.max_amount_per_symbol == 5_000_000
        assert limits.max_daily_loss_amount == 1_000_000  # default


class TestRiskContext:
    def test_minimal_context(self):
        regime = _make_regime()
        ctx = RiskContext(
            market_regime_result=regime,
            session_state=TradingSessionState.REGULAR_MARKET,
            emergency_stop=False,
            live_trading_enabled=True,
            current_positions=frozenset(),
            pending_orders=frozenset(),
            today_realized_pnl=0,
            daily_loss_limit=1_000_000,
        )
        assert ctx.live_trading_enabled is True
        assert ctx.emergency_stop is False

    def test_context_frozen(self):
        regime = _make_regime()
        ctx = RiskContext(
            market_regime_result=regime,
            session_state=TradingSessionState.REGULAR_MARKET,
            emergency_stop=False,
            live_trading_enabled=True,
            current_positions=frozenset(),
            pending_orders=frozenset(),
            today_realized_pnl=0,
            daily_loss_limit=1_000_000,
        )
        with pytest.raises(Exception):
            ctx.emergency_stop = True  # type: ignore
