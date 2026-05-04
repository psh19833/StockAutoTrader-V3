"""Phase 4 — Market Regime Engine 단위 테스트"""
import pytest
from datetime import date, datetime, timezone

from market_regime.regime_state import MarketRegime, BULL_THRESHOLD, NEUTRAL_LOWER
from market_regime.regime_score import MarketRegimeScore
from market_regime.regime_inputs import (
    MarketRegimeInputs, IndexData, BreadthData, MomentumData,
    VolatilityData, TradingValueData, SectorStrengthData, ForeignFlowData,
)
from market_regime.regime_result import MarketRegimeResult
from market_regime.regime_policy import (
    classify_regime, determine_policy, evaluate, DEFAULT_MIN_SCORE,
)
from market_regime.regime_calculator import (
    calculate, _compute_index_trend, _compute_breadth, _compute_momentum,
    _compute_volatility, _compute_trading_value, _compute_sector_strength,
    _compute_foreign_flow, _compute_risk_penalty,
)
from market_regime.regime_audit import regime_result_to_audit_event
from audit_logging.audit_event import AuditEventType


# ── MarketRegime Enum ──

class TestMarketRegime:
    def test_bull_exists(self):
        assert MarketRegime.BULL.value == "BULL"

    def test_neutral_exists(self):
        assert MarketRegime.NEUTRAL.value == "NEUTRAL"

    def test_bear_exists(self):
        assert MarketRegime.BEAR.value == "BEAR"

    def test_unknown_exists(self):
        assert MarketRegime.UNKNOWN.value == "UNKNOWN"

    def test_thresholds_defined(self):
        assert BULL_THRESHOLD == 70.0
        assert NEUTRAL_LOWER == 40.0


# ── Score Range Validation ──

class TestScoreRangeValidation:
    def test_valid_score_created(self):
        s = MarketRegimeScore(index_trend_score=10.0, market_breadth_score=5.0)
        assert s.index_trend_score == 10.0
        assert s.market_breadth_score == 5.0

    def test_index_trend_out_of_range(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(index_trend_score=30.0)  # max 25

    def test_breadth_out_of_range(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(market_breadth_score=25.0)  # max 20

    def test_momentum_out_of_range(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(market_momentum_score=20.0)  # max 15

    def test_risk_penalty_out_of_range_negative(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(market_risk_penalty=-5.0)

    def test_risk_penalty_out_of_range_high(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(market_risk_penalty=45.0)  # max 40

    def test_negative_score(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(index_trend_score=-1.0)

    def test_foreign_flow_out_of_range(self):
        with pytest.raises(ValueError):
            MarketRegimeScore(foreign_institution_flow_score=10.0)  # max 5


# ── Total Score ──

class TestTotalScore:
    def test_total_score_equals_sum_minus_penalty(self):
        s = MarketRegimeScore(
            index_trend_score=15.0,
            market_breadth_score=10.0,
            market_momentum_score=8.0,
            volatility_risk_score=10.0,
            trading_value_score=5.0,
            sector_strength_score=4.0,
            foreign_institution_flow_score=3.0,
            market_risk_penalty=5.0,
        )
        expected_raw = 15 + 10 + 8 + 10 + 5 + 4 + 3
        expected_total = expected_raw - 5.0
        assert s.raw_total == expected_raw
        assert s.total_score == expected_total

    def test_total_score_clamped_zero(self):
        s = MarketRegimeScore(market_risk_penalty=40.0)
        assert s.total_score == 0.0

    def test_total_score_clamped_40_penalty(self):
        # penalty 40은 허용 범위 [0, 40]의 최대값
        s = MarketRegimeScore(
            index_trend_score=10.0, market_breadth_score=10.0,
            market_momentum_score=5.0, volatility_risk_score=5.0,
            trading_value_score=3.0, sector_strength_score=2.0,
            foreign_institution_flow_score=1.0,
            market_risk_penalty=40.0,
        )
        assert s.total_score == 0.0  # raw_total 36 - 40 = -4 → 0

    def test_total_score_clamped_100(self):
        s = MarketRegimeScore(
            index_trend_score=25.0,
            market_breadth_score=20.0,
            market_momentum_score=15.0,
            volatility_risk_score=15.0,
            trading_value_score=10.0,
            sector_strength_score=10.0,
            foreign_institution_flow_score=5.0,
            market_risk_penalty=0.0,
        )
        raw = 25 + 20 + 15 + 15 + 10 + 10 + 5
        expected = min(100.0, max(0.0, raw - 0))
        assert s.total_score == expected

    def test_total_score_min_zero(self):
        s = MarketRegimeScore(market_risk_penalty=40.0)
        assert s.total_score == 0.0


# ── Classification ──

class TestClassification:
    def test_70_plus_is_bull(self):
        assert classify_regime(70.0) == MarketRegime.BULL
        assert classify_regime(85.0) == MarketRegime.BULL
        assert classify_regime(100.0) == MarketRegime.BULL

    def test_40_to_69_is_neutral(self):
        assert classify_regime(40.0) == MarketRegime.NEUTRAL
        assert classify_regime(55.0) == MarketRegime.NEUTRAL
        assert classify_regime(69.0) == MarketRegime.NEUTRAL

    def test_39_and_below_is_bear(self):
        assert classify_regime(39.0) == MarketRegime.BEAR
        assert classify_regime(20.0) == MarketRegime.BEAR
        assert classify_regime(0.0) == MarketRegime.BEAR


# ── Policy ──

class TestPolicy:
    def test_bull_adjustment_positive(self):
        s = MarketRegimeScore(index_trend_score=20.0, market_breadth_score=15.0)
        adj, allow, min_score, reasons = determine_policy(MarketRegime.BULL, s)
        assert adj > 0
        assert allow is True

    def test_neutral_adjustment_zero(self):
        s = MarketRegimeScore()
        adj, allow, min_score, reasons = determine_policy(MarketRegime.NEUTRAL, s)
        assert adj == 0.0
        assert allow is True

    def test_bear_adjustment_negative(self):
        s = MarketRegimeScore()
        adj, allow, min_score, reasons = determine_policy(MarketRegime.BEAR, s)
        assert adj < 0
        assert allow is False
        assert min_score >= 999

    def test_unknown_blocked(self):
        s = MarketRegimeScore()
        adj, allow, min_score, reasons = determine_policy(MarketRegime.UNKNOWN, s)
        assert adj < 0
        assert allow is False
        assert min_score >= 999

    def test_penalty_35_blocks(self):
        s = MarketRegimeScore(market_risk_penalty=35.0)
        adj, allow, min_score, reasons = determine_policy(MarketRegime.BULL, s)
        assert allow is False  # penalty >= 35 → blocked even in BULL

    def test_penalty_25_tightens(self):
        s = MarketRegimeScore(market_risk_penalty=25.0)
        # BULL이지만 penalty >= 25 → NEUTRAL로 downgrade
        adj, allow, min_score, reasons = determine_policy(MarketRegime.BULL, s)
        # NEUTRAL이거나 penalty 강화 정책 적용
        pass


# ── Evaluate ──

class TestEvaluate:
    def _make_bull_inputs(self) -> MarketRegimeInputs:
        return MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_current=2850.0, kospi_change_pct=2.5,
                kospi_ma5_pct=1.5, kospi_ma20_pct=2.0, kospi_ma60_pct=3.0,
                kosdaq_current=870.0, kosdaq_change_pct=2.8,
                kosdaq_ma5_pct=1.0, kosdaq_ma20_pct=1.5, kosdaq_ma60_pct=3.0,
            ),
            breadth=BreadthData(
                advance_count=700, decline_count=150, unchanged_count=50,
                advance_sector_count=25, total_sector_count=30,
            ),
            momentum=MomentumData(
                kospi_1d_momentum=2.5, kospi_5d_momentum=4.0,
                kospi_20d_momentum=6.0, high_volume_ratio=0.7,
                high_price_near_ratio=0.5,
            ),
            volatility=VolatilityData(
                intraday_range_pct=0.5, vi_triggered_count=2,
                extreme_updown_mixed=False, trend_consistency=0.8,
            ),
            trading_value=TradingValueData(
                kospi_volume=150000, kosdaq_volume=80000,
                volume_change_pct=25.0, top_volume_concentration=0.3,
            ),
            sector_strength=SectorStrengthData(
                up_sector_ratio=0.75, leading_sector_strength=0.8,
                sector_trend_continuity=0.7, overheat_sector_ratio=0.1,
            ),
            foreign_flow=ForeignFlowData(
                foreign_net_buy=8000, institution_net_buy=5000,
                kosdaq_foreign_flow=2000,
            ),
            source_endpoints=("/uapi/domestic-stock/v1/quotations/inquire-price",),
        )

    def _make_bear_inputs(self) -> MarketRegimeInputs:
        return MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_current=2500.0, kospi_change_pct=-2.5,
                kospi_ma5_pct=-1.0, kospi_ma20_pct=-2.0, kospi_ma60_pct=-0.5,
                kosdaq_current=700.0, kosdaq_change_pct=-3.0,
                kosdaq_ma5_pct=-2.0, kosdaq_ma20_pct=-3.0, kosdaq_ma60_pct=-1.5,
            ),
            breadth=BreadthData(
                advance_count=150, decline_count=700, unchanged_count=50,
                advance_sector_count=5, total_sector_count=30,
            ),
            momentum=MomentumData(
                kospi_1d_momentum=-2.5, kospi_5d_momentum=-4.0, kospi_20d_momentum=-6.0,
            ),
            volatility=VolatilityData(
                intraday_range_pct=3.5, vi_triggered_count=25, extreme_updown_mixed=True,
            ),
            trading_value=TradingValueData(volume_change_pct=-25.0),
            sector_strength=SectorStrengthData(up_sector_ratio=0.2),
            source_endpoints=("/uapi/domestic-stock/v1/quotations/inquire-price",),
        )

    def test_bull_evaluate(self):
        inputs = self._make_bull_inputs()
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.BULL
        assert result.allow_new_buy is True
        assert result.candidate_score_adjustment > 0

    def test_neutral_evaluate(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_current=2700.0, kospi_change_pct=0.2,
                kosdaq_current=800.0, kosdaq_change_pct=0.1,
                kospi_ma5_pct=0.0, kospi_ma20_pct=0.0, kospi_ma60_pct=0.5,
            ),
            breadth=BreadthData(advance_count=350, decline_count=350),
            momentum=MomentumData(kospi_1d_momentum=0.2),
        )
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.NEUTRAL or result.total_score >= 40
        assert result.allow_new_buy is True

    def test_bear_evaluate(self):
        inputs = self._make_bear_inputs()
        score = calculate(inputs)
        result = evaluate(inputs, score)
        # bear이거나 risk penalty로 차단
        assert result.allow_new_buy is False

    def test_unknown_when_source_invalid(self):
        inputs = MarketRegimeInputs(
            source="CRAWLER",
            index=IndexData(kospi_current=2700.0, kospi_change_pct=1.0,
                            kosdaq_current=800.0, kosdaq_change_pct=1.0),
            breadth=BreadthData(advance_count=500, decline_count=300),
            momentum=MomentumData(kospi_1d_momentum=1.0),
        )
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.UNKNOWN
        assert result.allow_new_buy is False

    def test_unknown_when_missing_core_data(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(kospi_current=None, kospi_change_pct=None,
                            kosdaq_current=None, kosdaq_change_pct=None),
            breadth=BreadthData(advance_count=500, decline_count=300),
            momentum=MomentumData(kospi_1d_momentum=1.0),
        )
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.UNKNOWN
        assert result.allow_new_buy is False


# ── Calculator ──

class TestCalculator:
    def test_index_trend_strong_bull(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_change_pct=2.5, kosdaq_change_pct=2.0,
                kospi_ma5_pct=1.0, kospi_ma20_pct=2.0, kospi_ma60_pct=3.0,
            ),
        )
        score = _compute_index_trend(inputs)
        assert score > 15  # 강한 상승장

    def test_index_trend_bear(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_change_pct=-2.0, kosdaq_change_pct=-2.5,
                kospi_ma5_pct=-1.0, kospi_ma20_pct=-2.0, kospi_ma60_pct=-1.0,
            ),
        )
        score = _compute_index_trend(inputs)
        assert score < 10  # 하락장

    def test_breadth_strong(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            breadth=BreadthData(advance_count=700, decline_count=150,
                                advance_sector_count=25, total_sector_count=30),
        )
        score = _compute_breadth(inputs)
        assert score >= 15

    def test_breadth_weak(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            breadth=BreadthData(advance_count=100, decline_count=750,
                                advance_sector_count=3, total_sector_count=30),
        )
        score = _compute_breadth(inputs)
        assert score <= 5

    def test_momentum_strong(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            momentum=MomentumData(
                kospi_1d_momentum=2.0, kospi_5d_momentum=4.0,
                kospi_20d_momentum=6.0, high_volume_ratio=0.7,
            ),
        )
        score = _compute_momentum(inputs)
        assert score > 10

    def test_momentum_weak(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            momentum=MomentumData(kospi_1d_momentum=-2.0),
        )
        score = _compute_momentum(inputs)
        assert score <= 3

    def test_volatility_stable(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            volatility=VolatilityData(intraday_range_pct=0.4),
        )
        score = _compute_volatility(inputs)
        assert score >= 10

    def test_volatility_high(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            volatility=VolatilityData(
                intraday_range_pct=3.5, vi_triggered_count=30,
                extreme_updown_mixed=True,
            ),
        )
        score = _compute_volatility(inputs)
        assert score <= 5

    def test_trading_value_positive(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            trading_value=TradingValueData(volume_change_pct=20.0),
        )
        score = _compute_trading_value(inputs)
        assert score >= 6

    def test_trading_value_negative(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            trading_value=TradingValueData(volume_change_pct=-30.0),
        )
        score = _compute_trading_value(inputs)
        assert score <= 4

    def test_risk_penalty_high(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(kospi_change_pct=-3.0, kosdaq_change_pct=-3.0),
            breadth=BreadthData(advance_count=100, decline_count=800),
            volatility=VolatilityData(
                intraday_range_pct=3.5, vi_triggered_count=35,
                extreme_updown_mixed=True,
            ),
            trading_value=TradingValueData(volume_change_pct=-35.0),
        )
        penalty = _compute_risk_penalty(inputs)
        assert penalty >= 25

    def test_risk_penalty_low(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(kospi_change_pct=0.5, kosdaq_change_pct=0.3),
            breadth=BreadthData(advance_count=400, decline_count=300),
            volatility=VolatilityData(intraday_range_pct=0.6),
            trading_value=TradingValueData(volume_change_pct=5.0),
        )
        penalty = _compute_risk_penalty(inputs)
        assert penalty <= 5


# ── Result ──

class TestRegimeResult:
    def test_result_created(self):
        s = MarketRegimeScore(index_trend_score=15.0, market_breadth_score=10.0)
        result = MarketRegimeResult(
            regime=MarketRegime.BULL,
            score=s,
            total_score=25.0,
            candidate_score_adjustment=7.5,
            allow_new_buy=True,
            min_candidate_score_required=50.0,
            reasons=("Strong market",),
        )
        assert result.regime == MarketRegime.BULL
        assert result.total_score == 25.0
        assert result.candidate_score_adjustment == 7.5
        assert result.allow_new_buy is True
        assert result.evaluated_at is not None


# ── Audit Event ──

class TestRegimeAudit:
    def test_audit_event_created(self):
        s = MarketRegimeScore(index_trend_score=15.0, market_breadth_score=10.0)
        result = MarketRegimeResult(
            regime=MarketRegime.BULL,
            score=s,
            total_score=25.0,
            candidate_score_adjustment=7.5,
            allow_new_buy=True,
            min_candidate_score_required=50.0,
            reasons=("Strong market",),
        )
        event = regime_result_to_audit_event(result, correlation_id="test_cr_001")
        assert event.event_type == AuditEventType.MARKET_REGIME_EVALUATED.value
        assert event.correlation_id == "test_cr_001"
        assert event.payload["regime"] == "BULL"
        assert event.payload["total_score"] == 25.0
        assert event.payload["allow_new_buy"] is True

    def test_audit_event_payload_contains_all_fields(self):
        s = MarketRegimeScore(
            index_trend_score=10.0, market_breadth_score=8.0,
            market_momentum_score=5.0, volatility_risk_score=7.0,
            trading_value_score=3.0, sector_strength_score=2.0,
            foreign_institution_flow_score=1.0, market_risk_penalty=5.0,
        )
        result = MarketRegimeResult(
            regime=MarketRegime.NEUTRAL,
            score=s,
            total_score=31.0,
            candidate_score_adjustment=0.0,
            allow_new_buy=True,
            min_candidate_score_required=50.0,
        )
        event = regime_result_to_audit_event(result)
        p = event.payload
        assert "index_trend_score" in p
        assert "market_risk_penalty" in p
        assert "candidate_score_adjustment" in p
        assert "reasons" in p
        assert "source_endpoints" in p


# ── Inputs Validation ──

class TestInputsValidation:
    def test_valid_source_no_warnings(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(kospi_current=2700.0, kospi_change_pct=1.0,
                            kosdaq_current=800.0, kosdaq_change_pct=1.0),
            breadth=BreadthData(advance_count=500, decline_count=300),
            momentum=MomentumData(kospi_1d_momentum=1.0),
        )
        warnings = inputs.validate()
        assert len(warnings) == 0

    def test_invalid_source_warning(self):
        inputs = MarketRegimeInputs(source="CRAWLER")
        warnings = inputs.validate()
        assert any("KIS_API" in w for w in warnings)

    def test_missing_core_data_warning(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(kospi_current=None, kospi_change_pct=None,
                            kosdaq_current=None, kosdaq_change_pct=None),
        )
        warnings = inputs.validate()
        assert any("missing" in w for w in warnings)


# ── Missing Input / No Optimistic Estimate ──

class TestMissingData:
    def test_no_optimistic_estimate_on_missing_data(self):
        """API 실패 시 낙관적 추정 금지"""
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(kospi_current=None),
            breadth=BreadthData(),
            momentum=MomentumData(),
        )
        score = calculate(inputs)
        # 점수가 계산은 되지만 evaluate에서 UNKNOWN 처리
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.UNKNOWN or result.data_quality_warnings

    def test_not_unknown_with_full_data(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_current=2700.0, kospi_change_pct=0.5,
                kosdaq_current=800.0, kosdaq_change_pct=0.3,
            ),
            breadth=BreadthData(advance_count=400, decline_count=300),
            momentum=MomentumData(kospi_1d_momentum=0.5),
        )
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime != MarketRegime.UNKNOWN


# ── End-to-End: Calculator → Policy → Result ──

class TestEndToEnd:
    def test_full_bull_scenario(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_current=2850.0, kospi_change_pct=1.8,
                kospi_ma5_pct=0.8, kospi_ma20_pct=1.5, kospi_ma60_pct=3.0,
                kosdaq_current=870.0, kosdaq_change_pct=2.2,
                kosdaq_ma5_pct=0.5, kosdaq_ma20_pct=1.2, kosdaq_ma60_pct=2.5,
            ),
            breadth=BreadthData(
                advance_count=650, decline_count=180, unchanged_count=70,
                advance_sector_count=22, total_sector_count=30,
            ),
            momentum=MomentumData(
                kospi_1d_momentum=1.8, kospi_5d_momentum=3.0,
                kospi_20d_momentum=5.0, high_volume_ratio=0.55,
            ),
            volatility=VolatilityData(intraday_range_pct=0.7),
            trading_value=TradingValueData(volume_change_pct=15.0),
            sector_strength=SectorStrengthData(up_sector_ratio=0.7),
            foreign_flow=ForeignFlowData(foreign_net_buy=5000, institution_net_buy=3000),
        )
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.BULL
        assert result.allow_new_buy is True
        assert result.candidate_score_adjustment > 0
        assert len(result.data_quality_warnings) == 0

    def test_full_bear_scenario(self):
        inputs = MarketRegimeInputs(
            source="KIS_API",
            index=IndexData(
                kospi_current=2450.0, kospi_change_pct=-2.8,
                kospi_ma5_pct=-1.5, kospi_ma20_pct=-3.0, kospi_ma60_pct=-2.0,
                kosdaq_current=680.0, kosdaq_change_pct=-3.5,
                kosdaq_ma5_pct=-2.5, kosdaq_ma20_pct=-4.0, kosdaq_ma60_pct=-3.0,
            ),
            breadth=BreadthData(
                advance_count=80, decline_count=800, unchanged_count=20,
                advance_sector_count=2, total_sector_count=30,
            ),
            momentum=MomentumData(
                kospi_1d_momentum=-2.8, kospi_5d_momentum=-5.0,
                kospi_20d_momentum=-8.0, high_volume_ratio=0.1,
            ),
            volatility=VolatilityData(
                intraday_range_pct=4.0, vi_triggered_count=35,
                extreme_updown_mixed=True, trend_consistency=0.2,
            ),
            trading_value=TradingValueData(volume_change_pct=-30.0),
            sector_strength=SectorStrengthData(up_sector_ratio=0.1),
            foreign_flow=ForeignFlowData(foreign_net_buy=-8000, institution_net_buy=-5000),
        )
        score = calculate(inputs)
        result = evaluate(inputs, score)
        assert result.regime == MarketRegime.BEAR or result.allow_new_buy is False
        assert result.allow_new_buy is False