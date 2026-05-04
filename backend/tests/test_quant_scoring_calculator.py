"""Tests for Scoring Calculator"""
from __future__ import annotations

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate
from market_regime.regime_state import MarketRegime
from market_regime.regime_result import MarketRegimeResult
from market_regime.regime_score import MarketRegimeScore
from quant.scoring_calculator import (
    evaluate_candidate,
    compute_common_scores,
    compute_rapid_surge_scores,
    compute_pullback_scores,
    determine_decision,
    DEFAULT_COMMON_WEIGHTS,
)


def _make_candidate(
    scanner_type: ScannerType = ScannerType.RAPID_SURGE,
    included: bool = True,
    metrics: dict | None = None,
) -> ScannerCandidate:
    m = metrics or {}
    return ScannerCandidate(
        symbol="005930",
        market="KOSPI",
        product_type="COMMON_STOCK",
        scanner_type=scanner_type,
        discovered_reason=("test",),
        metrics=m,
        source_endpoints=("kis/quote",),
        source="KIS_API",
        scan_run_id="scan_001",
        included=included,
    )


def _make_regime_result(
    regime: MarketRegime = MarketRegime.NEUTRAL,
    adjustment: float = 0.0,
    allow_new_buy: bool = True,
    min_score: float = 50.0,
) -> MarketRegimeResult:
    score = MarketRegimeScore(
        index_trend_score=20.0,
        market_breadth_score=15.0,
        market_momentum_score=10.0,
        volatility_risk_score=10.0,
        trading_value_score=7.0,
        sector_strength_score=7.0,
        foreign_institution_flow_score=3.0,
        market_risk_penalty=0.0,
    )
    return MarketRegimeResult(
        regime=regime,
        score=score,
        total_score=score.total_score,
        candidate_score_adjustment=adjustment,
        allow_new_buy=allow_new_buy,
        min_candidate_score_required=min_score,
    )


class TestCommonScores:
    """공통 점수 계산"""

    def test_default_weights(self):
        assert isinstance(DEFAULT_COMMON_WEIGHTS, dict)
        assert "liquidity" in DEFAULT_COMMON_WEIGHTS

    def test_high_liquidity_score(self):
        metrics = {
            "trading_value": 100_000_000_000,  # 100B
            "trading_value_rank": 5,
        }
        scores = compute_common_scores(metrics)
        assert scores["liquidity_score"] >= 8.0

    def test_low_liquidity_score(self):
        metrics = {
            "trading_value": 500_000_000,  # 500M
            "trading_value_rank": 500,
        }
        scores = compute_common_scores(metrics)
        assert scores["liquidity_score"] < 5.0

    def test_tight_spread_score(self):
        metrics = {"spread_rate": 0.01}
        scores = compute_common_scores(metrics)
        assert scores["spread_score"] >= 8.0

    def test_wide_spread_score(self):
        metrics = {"spread_rate": 0.5}
        scores = compute_common_scores(metrics)
        assert scores["spread_score"] <= 5.0

    def test_high_volume_score(self):
        metrics = {"volume": 5_000_000, "volume_ratio_vs_recent_avg": 3.0}
        scores = compute_common_scores(metrics)
        assert scores["volume_score"] >= 7.0

    def test_zero_volume_score(self):
        metrics = {"volume": 0, "volume_ratio_vs_recent_avg": 0}
        scores = compute_common_scores(metrics)
        assert scores["volume_score"] == 0.0

    def test_high_momentum_score(self):
        metrics = {
            "intraday_change_rate": 5.0,
            "execution_strength": 150.0,
        }
        scores = compute_common_scores(metrics)
        assert scores["momentum_score"] >= 6.0

    def test_negative_change_momentum_score(self):
        metrics = {
            "intraday_change_rate": -3.0,
            "execution_strength": 50.0,
        }
        scores = compute_common_scores(metrics)
        assert scores["momentum_score"] <= 4.0

    def test_trend_score_near_high(self):
        metrics = {
            "current_price": 50000,
            "intraday_high": 51000,
            "recent_high_20d": 48000,
        }
        scores = compute_common_scores(metrics)
        assert scores["trend_score"] >= 5.0

    def test_trend_score_far_from_high(self):
        metrics = {
            "current_price": 40000,
            "intraday_high": 51000,
            "recent_high_20d": 49000,
        }
        scores = compute_common_scores(metrics)
        # price=40000, high=51000 → proximity=0.784 → trend≈7.8
        # 시세 추세 자체는 강하지만 고점 근접도로 인해 점수는 높게 나옴
        assert 7.0 <= scores["trend_score"] <= 9.0

    def test_volatility_safety_low_beta(self):
        metrics = {"volatility_ratio": 0.5}
        scores = compute_common_scores(metrics)
        assert scores["volatility_safety_score"] >= 7.0

    def test_volatility_safety_high_beta(self):
        metrics = {"volatility_ratio": 3.0}
        scores = compute_common_scores(metrics)
        assert scores["volatility_safety_score"] <= 3.0

    def test_missing_metrics_default_low(self):
        scores = compute_common_scores({})
        for key in ["liquidity_score", "spread_score", "volume_score",
                     "momentum_score", "trend_score", "orderbook_score"]:
            assert scores[key] <= 3.0  # 정보 없음 = 낮은 점수
        # volatility_safety는 기본값 1.0에서 7.0 (보수적 계산)
        assert scores["volatility_safety_score"] >= 5.0


class TestRapidSurgeScores:
    """RAPID_SURGE 전용 점수"""

    def test_high_surge_velocity(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 10.0,
            "volume_ratio_vs_recent_avg": 5.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 0.5,
        })
        assert scores["surge_velocity_score"] >= 7.0

    def test_moderate_surge(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 2.0,
            "volume_ratio_vs_recent_avg": 1.5,
            "current_price": 50000,
            "intraday_high": 51000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 0.5,
        })
        assert scores["surge_velocity_score"] < 7.0

    def test_volume_burst_high(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 5.0,
            "volume_ratio_vs_recent_avg": 10.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 0.5,
        })
        assert scores["volume_burst_score"] >= 8.0

    def test_intraday_high_proximity_touching(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 5.0,
            "volume_ratio_vs_recent_avg": 3.0,
            "current_price": 51000,
            "intraday_high": 51000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 0.0,
        })
        assert scores["intraday_high_proximity_score"] >= 9.0

    def test_vi_proximity_active(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 5.0,
            "volume_ratio_vs_recent_avg": 3.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "vi_status": "ACTIVE",
            "pullback_from_high": 0.5,
        })
        assert scores["vi_proximity_penalty"] >= 5.0

    def test_vi_inactive_no_penalty(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 5.0,
            "volume_ratio_vs_recent_avg": 3.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 0.5,
        })
        assert scores["vi_proximity_penalty"] == 0.0

    def test_pullback_failure_penalty(self):
        scores = compute_rapid_surge_scores({
            "intraday_change_rate": 5.0,
            "volume_ratio_vs_recent_avg": 3.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 8.0,  # 큰 폭 하락
        })
        assert scores["pullback_failure_penalty"] >= 5.0


class TestPullbackScores:
    """PULLBACK_REBOUND 전용 점수"""

    def test_high_prior_strength(self):
        scores = compute_pullback_scores({
            "prior_intraday_gain": 8.0,
            "pullback_from_high": 2.0,
            "rebound_volume_ratio": 2.0,
            "support_holding_score": 8.0,
        })
        assert scores["prior_strength_score"] >= 7.0

    def test_shallow_pullback_good(self):
        scores = compute_pullback_scores({
            "prior_intraday_gain": 5.0,
            "pullback_from_high": 1.5,
            "rebound_volume_ratio": 2.0,
            "support_holding_score": 8.0,
        })
        assert scores["pullback_depth_score"] >= 7.0

    def test_deep_pullback_low_score(self):
        scores = compute_pullback_scores({
            "prior_intraday_gain": 5.0,
            "pullback_from_high": 8.0,
            "rebound_volume_ratio": 2.0,
            "support_holding_score": 8.0,
        })
        assert scores["pullback_depth_score"] <= 4.0

    def test_strong_rebound_confirmation(self):
        scores = compute_pullback_scores({
            "prior_intraday_gain": 5.0,
            "pullback_from_high": 2.0,
            "rebound_volume_ratio": 3.0,
            "support_holding_score": 8.0,
        })
        assert scores["rebound_confirmation_score"] >= 7.0

    def test_high_support_holding(self):
        scores = compute_pullback_scores({
            "prior_intraday_gain": 5.0,
            "pullback_from_high": 2.0,
            "rebound_volume_ratio": 2.0,
            "support_holding_score": 9.0,
        })
        assert scores["support_holding_score"] >= 8.0

    def test_low_support_holding(self):
        scores = compute_pullback_scores({
            "prior_intraday_gain": 5.0,
            "pullback_from_high": 2.0,
            "rebound_volume_ratio": 2.0,
            "support_holding_score": 2.0,
        })
        assert scores["support_holding_score"] <= 3.0


class TestDecision:
    """최종 Decision 결정"""

    def test_pass_above_threshold(self):
        decision, reasons = determine_decision(
            final_score=60.0, regime_result=_make_regime_result(),
            pass_threshold=50.0, watch_threshold=25.0,
        )
        assert decision == "PASS"

    def test_watch_between_thresholds(self):
        decision, reasons = determine_decision(
            final_score=35.0, regime_result=_make_regime_result(),
            pass_threshold=50.0, watch_threshold=25.0,
        )
        assert decision == "WATCH"

    def test_reject_below_watch(self):
        decision, reasons = determine_decision(
            final_score=10.0, regime_result=_make_regime_result(),
            pass_threshold=50.0, watch_threshold=25.0,
        )
        assert decision == "REJECT"

    def test_bear_reject(self):
        result = _make_regime_result(
            regime=MarketRegime.BEAR, allow_new_buy=False
        )
        decision, reasons = determine_decision(
            final_score=60.0, regime_result=result,
            pass_threshold=50.0, watch_threshold=25.0,
        )
        assert decision == "REJECT"

    def test_unknown_reject(self):
        result = _make_regime_result(
            regime=MarketRegime.UNKNOWN, allow_new_buy=False
        )
        decision, reasons = determine_decision(
            final_score=60.0, regime_result=result,
            pass_threshold=50.0, watch_threshold=25.0,
        )
        assert decision == "REJECT"

    def test_reject_has_reason(self):
        result = _make_regime_result(
            regime=MarketRegime.BEAR, allow_new_buy=False
        )
        decision, reasons = determine_decision(
            final_score=60.0, regime_result=result,
            pass_threshold=50.0, watch_threshold=25.0,
        )
        assert len(reasons) > 0
        assert "bear" in reasons[0].lower() or "blocked" in reasons[0].lower()


class TestEvaluateCandidate:
    """전체 후보 평가"""

    def test_rapid_surge_passes(self):
        candidate = _make_candidate(
            ScannerType.RAPID_SURGE,
            metrics={
                "trading_value": 50_000_000_000,
                "trading_value_rank": 10,
                "spread_rate": 0.02,
                "volume": 2_000_000,
                "volume_ratio_vs_recent_avg": 3.0,
                "intraday_change_rate": 5.0,
                "execution_strength": 130.0,
                "current_price": 50000,
                "intraday_high": 51000,
                "recent_high_20d": 48000,
                "vi_status": "INACTIVE",
                "pullback_from_high": 0.5,
                "volatility_ratio": 1.0,
            }
        )
        result = _make_regime_result(
            regime=MarketRegime.BULL, adjustment=5.0, allow_new_buy=True,
        )
        score = evaluate_candidate(candidate, result)
        assert score.decision == "PASS"
        assert score.final_score >= 50.0
        assert score.surge_velocity_score > 0
        assert score.volume_burst_score > 0
        assert score.source_endpoints == ("kis/quote",)

    def test_neutral_watch(self):
        candidate = _make_candidate(
            ScannerType.RAPID_SURGE,
            metrics={
                "trading_value": 5_000_000_000,
                "trading_value_rank": 50,
                "spread_rate": 0.1,
                "volume": 500_000,
                "volume_ratio_vs_recent_avg": 1.5,
                "intraday_change_rate": 2.0,
                "execution_strength": 100.0,
                "current_price": 50000,
                "intraday_high": 51000,
                "recent_high_20d": 48000,
                "vi_status": "INACTIVE",
                "pullback_from_high": 0.5,
                "volatility_ratio": 1.5,
            }
        )
        result = _make_regime_result(
            regime=MarketRegime.NEUTRAL, adjustment=0.0, allow_new_buy=True,
        )
        score = evaluate_candidate(candidate, result)
        assert score.decision in ("WATCH", "REJECT")

    def test_bear_rejected(self):
        candidate = _make_candidate(metrics={
            "trading_value": 50_000_000_000,
            "spread_rate": 0.02,
            "volume": 2_000_000,
            "volume_ratio_vs_recent_avg": 3.0,
            "intraday_change_rate": 5.0,
            "execution_strength": 130.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "recent_high_20d": 48000,
            "vi_status": "INACTIVE",
            "pullback_from_high": 0.5,
            "volatility_ratio": 1.0,
        })
        result = _make_regime_result(
            regime=MarketRegime.BEAR, adjustment=-15.0,
            allow_new_buy=False, min_score=999.0,
        )
        score = evaluate_candidate(candidate, result)
        assert score.decision == "REJECT"
        assert "blocked" in str(score.reasons).lower() or "bear" in str(score.reasons).lower()

    def test_unknown_rejected(self):
        candidate = _make_candidate(metrics={
            "trading_value": 50_000_000_000,
            "spread_rate": 0.02,
            "volume": 2_000_000,
            "intraday_change_rate": 5.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "execution_strength": 130.0,
            "volatility_ratio": 1.0,
        })
        result = _make_regime_result(
            regime=MarketRegime.UNKNOWN, adjustment=-30.0,
            allow_new_buy=False, min_score=999.0,
        )
        score = evaluate_candidate(candidate, result)
        assert score.decision == "REJECT"
        assert "unknown" in str(score.reasons).lower()

    def test_pullback_evaluation(self):
        candidate = _make_candidate(
            ScannerType.PULLBACK_REBOUND,
            metrics={
                "trading_value": 30_000_000_000,
                "spread_rate": 0.03,
                "volume": 1_000_000,
                "intraday_change_rate": 2.0,
                "current_price": 50000,
                "intraday_high": 51000,
                "recent_high_20d": 48000,
                "volatility_ratio": 1.0,
                "prior_intraday_gain": 6.0,
                "pullback_from_high": 2.0,
                "rebound_volume_ratio": 2.0,
                "support_holding_score": 7.5,
            }
        )
        result = _make_regime_result(
            regime=MarketRegime.BULL, adjustment=5.0, allow_new_buy=True,
        )
        score = evaluate_candidate(candidate, result)
        assert score.prior_strength_score > 0
        assert score.pullback_depth_score > 0
        assert score.rebound_confirmation_score > 0
        assert score.support_holding_score > 0

    def test_symbol_risk_penalty(self):
        candidate = _make_candidate(metrics={
            "trading_value": 50_000_000_000,
            "spread_rate": 0.02,
            "volume": 2_000_000,
            "volume_ratio_vs_recent_avg": 3.0,
            "intraday_change_rate": 5.0,
            "execution_strength": 130.0,
            "current_price": 50000,
            "intraday_high": 51000,
            "recent_high_20d": 48000,
            "vi_status": "ACTIVE",
            "pullback_from_high": 0.5,
            "volatility_ratio": 1.0,
        })
        result = _make_regime_result()
        score = evaluate_candidate(candidate, result)
        assert score.symbol_risk_penalty > 0  # VI active → penalty

    def test_no_order_fields_in_score(self):
        candidate = _make_candidate()
        result = _make_regime_result()
        score = evaluate_candidate(candidate, result)
        assert not hasattr(score, "buy_signal")
        assert not hasattr(score, "sell_signal")
        assert not hasattr(score, "order_intent")
        assert not hasattr(score, "quantity")
        assert not hasattr(score, "stop_loss")
        assert not hasattr(score, "take_profit")

    def test_evaluation_retains_scan_run_id(self):
        candidate = _make_candidate()
        result = _make_regime_result()
        score = evaluate_candidate(candidate, result)
        assert score.scan_run_id == "scan_001"