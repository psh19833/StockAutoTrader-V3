"""Tests for QuantCandidateScore and QuantDecision models"""
from __future__ import annotations

from quant.candidate_score import QuantCandidateScore, QuantDecision


class TestQuantDecision:
    """QuantDecision enum tests"""

    def test_has_pass(self):
        assert QuantDecision.PASS == "PASS"

    def test_has_watch(self):
        assert QuantDecision.WATCH == "WATCH"

    def test_has_reject(self):
        assert QuantDecision.REJECT == "REJECT"

    def test_all_three_values(self):
        assert len(QuantDecision) == 3


class TestQuantCandidateScore:
    """QuantCandidateScore model tests"""

    def test_minimal_score(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
        )
        assert score.symbol == "005930"
        assert score.final_score == 0.0
        assert score.decision == QuantDecision.REJECT
        assert score.liquidity_score == 0.0
        assert score.spread_score == 0.0
        assert score.volume_score == 0.0
        assert score.momentum_score == 0.0
        assert score.trend_score == 0.0
        assert score.orderbook_score == 0.0
        assert score.volatility_safety_score == 0.0
        assert score.market_regime_adjustment == 0.0
        assert score.symbol_risk_penalty == 0.0
        assert score.reasons == ()

    def test_full_common_score(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            liquidity_score=8.0,
            spread_score=7.0,
            volume_score=9.0,
            momentum_score=6.0,
            trend_score=5.0,
            orderbook_score=8.0,
            volatility_safety_score=7.0,
            market_regime_adjustment=7.5,
            symbol_risk_penalty=0.0,
            final_score=57.5,
            decision=QuantDecision.PASS,
            reasons=("high_liquidity", "strong_momentum"),
        )
        assert score.liquidity_score == 8.0
        assert score.final_score == 57.5
        assert score.decision == QuantDecision.PASS
        assert "high_liquidity" in score.reasons

    def test_rapid_surge_specific_scores(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            final_score=45.0,
            decision=QuantDecision.WATCH,
            surge_velocity_score=8.0,
            volume_burst_score=9.0,
            intraday_high_proximity_score=7.0,
            vi_proximity_penalty=2.0,
            pullback_failure_penalty=1.0,
        )
        assert score.surge_velocity_score == 8.0
        assert score.volume_burst_score == 9.0
        assert score.intraday_high_proximity_score == 7.0
        assert score.vi_proximity_penalty == 2.0
        assert score.pullback_failure_penalty == 1.0

    def test_pullback_specific_scores(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="PULLBACK_REBOUND",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            final_score=40.0,
            decision=QuantDecision.PASS,
            prior_strength_score=7.0,
            pullback_depth_score=6.0,
            rebound_confirmation_score=8.0,
            support_holding_score=7.5,
        )
        assert score.prior_strength_score == 7.0
        assert score.pullback_depth_score == 6.0
        assert score.rebound_confirmation_score == 8.0
        assert score.support_holding_score == 7.5

    def test_reject_decision(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            final_score=15.0,
            decision=QuantDecision.REJECT,
            reasons=("score_too_low", "market_regime_blocked"),
        )
        assert score.decision == QuantDecision.REJECT

    def test_watch_decision(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            final_score=30.0,
            decision=QuantDecision.WATCH,
        )
        assert score.decision == QuantDecision.WATCH

    def test_is_frozen(self):
        import pytest
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
        )
        with pytest.raises(AttributeError):
            score.final_score = 100.0

    def test_no_order_fields(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
        )
        assert not hasattr(score, "buy_signal")
        assert not hasattr(score, "sell_signal")
        assert not hasattr(score, "order_intent")
        assert not hasattr(score, "quantity")
        assert not hasattr(score, "stop_loss")
        assert not hasattr(score, "take_profit")

    def test_source_endpoints_preserved(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            source_endpoints=("kis/quote", "kis/rank"),
        )
        assert score.source_endpoints == ("kis/quote", "kis/rank")

    def test_data_quality_warnings_preserved(self):
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="RAPID_SURGE",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            data_quality_warnings=("missing_volume_ratio",),
        )
        assert "missing_volume_ratio" in score.data_quality_warnings

    def test_liquidity_momentum_works(self):
        """LIQUIDITY_MOMENTUM Type도 정상 동작"""
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="LIQUIDITY_MOMENTUM",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            final_score=50.0,
            decision=QuantDecision.PASS,
        )
        assert score.scanner_type == "LIQUIDITY_MOMENTUM"
        assert score.decision == QuantDecision.PASS

    def test_breakout_works(self):
        """BREAKOUT Type도 정상 동작"""
        score = QuantCandidateScore(
            symbol="005930",
            scanner_type="BREAKOUT",
            scan_run_id="scan_001",
            evaluation_id="eval_001",
            final_score=55.0,
            decision=QuantDecision.PASS,
        )
        assert score.scanner_type == "BREAKOUT"