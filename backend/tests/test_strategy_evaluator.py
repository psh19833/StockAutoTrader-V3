"""Tests for Strategy Evaluator"""
from __future__ import annotations

import pytest

from quant.candidate_score import QuantCandidateScore, QuantDecision
from scanner.scanner_types import ScannerType
from strategy.strategy_types import StrategyType
from strategy.strategy_evaluator import (
    evaluate_entry,
    evaluate_exit,
    map_scanner_to_strategy,
    compute_confidence,
)
from market_regime.regime_state import MarketRegime
from market_regime.regime_score import MarketRegimeScore
from market_regime.regime_result import MarketRegimeResult


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


def _make_score(decision=QuantDecision.PASS, symbol="005930",
                scanner_type="RAPID_SURGE", final_score=85.0, reasons=None):
    if reasons is None:
        reasons = ("strong_momentum",)
    return QuantCandidateScore(
        symbol=symbol, scanner_type=scanner_type,
        scan_run_id="scan_001", evaluation_id="eval_001",
        liquidity_score=8.0, spread_score=7.0, volume_score=6.0,
        momentum_score=9.0, trend_score=8.5, orderbook_score=5.0,
        volatility_safety_score=7.0, market_regime_adjustment=5.0,
        symbol_risk_penalty=2.0, final_score=final_score,
        decision=decision, reasons=reasons,
        surge_velocity_score=8.0, volume_burst_score=7.0,
        intraday_high_proximity_score=9.0, vi_proximity_penalty=0.0,
        pullback_failure_penalty=0.0, source_endpoints=("kis/quote",),
        data_quality_warnings=(),
    )


class TestMapScannerToStrategy:
    def test_rapid_surge_maps(self):
        assert map_scanner_to_strategy(ScannerType.RAPID_SURGE) == StrategyType.RAPID_SURGE_SCALPING

    def test_liquidity_momentum_maps(self):
        assert map_scanner_to_strategy(ScannerType.LIQUIDITY_MOMENTUM) == StrategyType.LIQUIDITY_MOMENTUM_FOLLOW

    def test_breakout_maps(self):
        assert map_scanner_to_strategy(ScannerType.BREAKOUT) == StrategyType.BREAKOUT_FOLLOW

    def test_pullback_rebound_maps(self):
        assert map_scanner_to_strategy(ScannerType.PULLBACK_REBOUND) == StrategyType.PULLBACK_REBOUND


class TestComputeConfidence:
    def test_high_score_high_confidence(self):
        conf = compute_confidence(final_score=85.0, decision=QuantDecision.PASS,
                                  liquidity_score=9.0, spread_score=9.0, momentum_score=9.0,
                                  symbol_risk_penalty=0.0)
        assert conf >= 0.7

    def test_low_score_low_confidence(self):
        conf = compute_confidence(final_score=55.0, decision=QuantDecision.PASS,
                                  liquidity_score=5.0, spread_score=5.0, momentum_score=5.0,
                                  symbol_risk_penalty=0.0)
        assert conf < 0.7

    def test_reject_zero_confidence(self):
        conf = compute_confidence(final_score=55.0, decision=QuantDecision.REJECT,
                                  liquidity_score=5.0, spread_score=5.0, momentum_score=5.0,
                                  symbol_risk_penalty=0.0)
        assert conf == 0.0

    def test_high_penalty_reduces_confidence(self):
        conf_with = compute_confidence(final_score=70.0, decision=QuantDecision.PASS,
                                       liquidity_score=8.0, spread_score=7.0, momentum_score=8.0,
                                       symbol_risk_penalty=8.0)
        conf_without = compute_confidence(final_score=70.0, decision=QuantDecision.PASS,
                                          liquidity_score=8.0, spread_score=7.0, momentum_score=8.0,
                                          symbol_risk_penalty=0.0)
        assert conf_with < conf_without


class TestEvaluateEntry:
    def test_pass_creates_buy_signal(self):
        score = _make_score(decision=QuantDecision.PASS)
        regime = _make_regime(MarketRegime.BULL)
        sig = evaluate_entry(score, regime)
        assert sig is not None
        assert sig.side == "BUY"
        assert sig.symbol == "005930"

    def test_reject_no_signal(self):
        score = _make_score(decision=QuantDecision.REJECT)
        regime = _make_regime(MarketRegime.BULL)
        sig = evaluate_entry(score, regime)
        assert sig is None

    def test_watch_no_signal(self):
        score = _make_score(decision=QuantDecision.WATCH)
        regime = _make_regime(MarketRegime.BULL)
        sig = evaluate_entry(score, regime)
        assert sig is None

    def test_bear_no_buy_signal(self):
        score = _make_score(decision=QuantDecision.PASS)
        regime = _make_regime(MarketRegime.BEAR, allow_new_buy=False)
        sig = evaluate_entry(score, regime)
        assert sig is None

    def test_unknown_no_buy_signal(self):
        score = _make_score(decision=QuantDecision.PASS)
        regime = _make_regime(MarketRegime.UNKNOWN, allow_new_buy=False)
        sig = evaluate_entry(score, regime)
        assert sig is None

    def test_signal_includes_scanner_type(self):
        score = _make_score(scanner_type="RAPID_SURGE")
        regime = _make_regime()
        sig = evaluate_entry(score, regime)
        assert sig.scanner_type == "RAPID_SURGE"

    def test_signal_includes_evidence(self):
        score = _make_score(reasons=("strong_momentum", "high_liquidity"))
        regime = _make_regime()
        sig = evaluate_entry(score, regime)
        assert len(sig.evidence) > 0


class TestEvaluateExit:
    def test_sell_signal_structure(self):
        """청산 신호 구조 검증"""
        sig = evaluate_exit(
            symbol="005930",
            strategy_type=StrategyType.FAST_EXIT,
            reason="time_exit",
            market_regime="BULL",
            source_quant_id="eval_002",
        )
        assert sig is not None
        assert sig.side == "SELL"
        assert sig.strategy_type == StrategyType.FAST_EXIT
        assert sig.symbol == "005930"
        assert sig.confidence > 0
