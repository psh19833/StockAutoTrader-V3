"""Tests for Quant Batch Evaluator — batch evaluation entry point"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate
from scanner.scan_result import ScanRunResult
from market_regime.regime_state import MarketRegime
from market_regime.regime_score import MarketRegimeScore
from market_regime.regime_result import MarketRegimeResult
from quant.candidate_score import QuantDecision
from quant.scoring_calculator import evaluate_candidates, evaluate_scan_result


# ── Helpers ──

def _make_regime_result(regime=MarketRegime.BULL, allow_new_buy=True,
                        adjustment=5.0, min_score=50.0):
    score = MarketRegimeScore(
        index_trend_score=15.0,
        market_breadth_score=10.0,
        market_momentum_score=10.0,
        volatility_risk_score=10.0,
        trading_value_score=8.0,
        sector_strength_score=8.0,
        foreign_institution_flow_score=4.0,
        market_risk_penalty=0.0,
    )
    return MarketRegimeResult(
        regime=regime,
        score=score,
        total_score=score.total_score,
        candidate_score_adjustment=adjustment,
        allow_new_buy=allow_new_buy,
        min_candidate_score_required=min_score,
        source_endpoints=("kis/index",),
    )


def _make_candidate(scanner_type=ScannerType.RAPID_SURGE, included=True,
                    symbol="005930", **metrics_override):
    base_metrics = {
        "current_price": 75000.0,
        "trading_value": 100_000_000_000,
        "volume": 10_000_000,
        "spread_rate": 0.1,
        "intraday_change_rate": 5.0,
        "volume_ratio_vs_recent_avg": 3.0,
        "execution_strength": 150.0,
        "intraday_high": 76000.0,
        "pullback_from_high": 1.0,
        "vi_status": "NONE",
        "volatility_ratio": 0.5,
        "is_trading_halted": False,
        "is_management_issue": False,
        "is_investment_warning": False,
    }
    base_metrics.update(metrics_override)
    return ScannerCandidate(
        symbol=symbol,
        market="KOSPI",
        product_type="COMMON_STOCK",
        scanner_type=scanner_type,
        symbol_name=f"Stock_{symbol}",
        metrics=base_metrics,
        source_endpoints=("kis/quote",),
        source="KIS_API",
        scan_run_id="scan_001",
        included=included,
    )


class TestEvaluateCandidates:
    """evaluate_candidates: ScannerCandidate 리스트 일괄 평가"""

    def test_batch_returns_all(self):
        candidates = [
            _make_candidate(symbol="005930"),
            _make_candidate(symbol="000660", scanner_type=ScannerType.LIQUIDITY_MOMENTUM,
                            intraday_change_rate=2.0, trading_value_rank=10),
        ]
        regime = _make_regime_result()
        results = evaluate_candidates(candidates, regime)
        assert len(results) == 2
        assert results[0].symbol == "005930"
        assert results[1].symbol == "000660"

    def test_excluded_candidates_evaluated(self):
        """제외된 후보도 평가에서 제외만 되고 결과는 생성된다"""
        candidates = [
            _make_candidate(included=True, symbol="A"),
            _make_candidate(included=False, symbol="B", excluded_reason="TEST"),
        ]
        regime = _make_regime_result()
        results = evaluate_candidates(candidates, regime)
        assert len(results) == 2

    def test_bear_regime_blocks_all(self):
        """BEAR 시장: allow_new_buy=False → 모든 후보 REJECT"""
        candidates = [_make_candidate()]
        regime = _make_regime_result(regime=MarketRegime.BEAR, allow_new_buy=False)
        results = evaluate_candidates(candidates, regime)
        assert results[0].decision == QuantDecision.REJECT
        assert "MarketRegimeBlocked" in results[0].reasons

    def test_high_score_pass(self):
        """고득점 후보 PASS"""
        candidates = [_make_candidate(
            trading_value=200_000_000_000,
            intraday_change_rate=10.0,
            volume_ratio_vs_recent_avg=10.0,
        )]
        regime = _make_regime_result(min_score=30.0)
        results = evaluate_candidates(candidates, regime)
        assert results[0].decision == QuantDecision.PASS

    def test_pullback_scanner_specific_scores(self):
        """PULLBACK_REBOUND 전용 점수 계산"""
        candidates = [_make_candidate(
            scanner_type=ScannerType.PULLBACK_REBOUND,
            prior_intraday_gain=5.0,
            pullback_from_high=2.0,
            rebound_volume_ratio=3.0,
            support_holding_score=7.0,
        )]
        regime = _make_regime_result()
        results = evaluate_candidates(candidates, regime)
        assert results[0].prior_strength_score > 0
        assert results[0].pullback_depth_score > 0

    def test_empty_list(self):
        results = evaluate_candidates([], _make_regime_result())
        assert results == []


class TestEvaluateScanResult:
    """evaluate_scan_result: ScanRunResult → 일괄 Quant 평가"""

    def test_full_pipeline(self):
        cand = _make_candidate()
        scan_result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="BULL",
            collected_count=1,
            included_count=1,
            candidates=(cand,),
            source_endpoints=("kis/quote",),
        )
        regime = _make_regime_result()
        results = evaluate_scan_result(scan_result, regime)
        assert len(results) == 1
        assert results[0].symbol == "005930"
        assert results[0].scanner_type == "RAPID_SURGE"

    def test_scan_result_with_mixed(self):
        """포함+제외 혼합 ScanRunResult"""
        included = _make_candidate(symbol="A", included=True)
        excluded = _make_candidate(symbol="B", included=False)
        scan_result = ScanRunResult(
            scan_run_id="scan_002",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="BULL",
            collected_count=2,
            included_count=1,
            excluded_count=1,
            candidates=(included, excluded),
        )
        regime = _make_regime_result()
        results = evaluate_scan_result(scan_result, regime)
        assert len(results) == 2

    def test_no_order_fields_in_results(self):
        """Quant 평가 결과에 주문 필드 없음"""
        cand = _make_candidate()
        scan_result = ScanRunResult(
            scan_run_id="scan_003",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="BULL",
            collected_count=1,
            included_count=1,
            candidates=(cand,),
        )
        regime = _make_regime_result()
        results = evaluate_scan_result(scan_result, regime)
        # QuantCandidateScore는 frozen dataclass이므로 dict 변환
        score_dict = results[0].__dict__
        forbidden = {"buy_signal", "sell_signal", "order_intent",
                     "quantity", "stop_loss", "take_profit", "execute_orders"}
        for key in forbidden:
            assert key not in score_dict
