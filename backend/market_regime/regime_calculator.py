"""MarketRegimeCalculator — MarketRegimeInputs → MarketRegimeScore 계산

외부 데이터나 추정값 사용 금지.
missing/invalid input이면 data_quality_warnings 기록.
"""
from __future__ import annotations

from market_regime.regime_inputs import MarketRegimeInputs
from market_regime.regime_score import MarketRegimeScore


def _compute_index_trend(inputs: MarketRegimeInputs) -> float:
    """Index Trend Score (0~25)

    KOSPI/KOSDAQ 추세, 이동평균선 관계, 등락률 기반.
    """
    idx = inputs.index
    score = 0.0

    # KOSPI 당일 등락 기반 (0~8)
    if idx.kospi_change_pct is not None:
        if idx.kospi_change_pct >= 2.0:
            score += 8.0
        elif idx.kospi_change_pct >= 1.0:
            score += 6.0
        elif idx.kospi_change_pct >= 0.3:
            score += 4.0
        elif idx.kospi_change_pct >= -0.3:
            score += 3.0
        elif idx.kospi_change_pct >= -1.0:
            score += 1.0
        # -1% 미만 → 0점

    # KOSDAQ 당일 등락 기반 (0~6)
    if idx.kosdaq_change_pct is not None:
        if idx.kosdaq_change_pct >= 2.0:
            score += 6.0
        elif idx.kosdaq_change_pct >= 1.0:
            score += 4.0
        elif idx.kosdaq_change_pct >= 0.3:
            score += 3.0
        elif idx.kosdaq_change_pct >= -0.3:
            score += 2.0
        elif idx.kosdaq_change_pct >= -1.0:
            score += 1.0

    # 이동평균선 관계 (0~7)
    if idx.kospi_ma5_pct is not None and idx.kospi_ma5_pct >= 0:
        score += 1.5
    if idx.kospi_ma20_pct is not None and idx.kospi_ma20_pct >= 0:
        score += 2.0
    if idx.kospi_ma60_pct is not None and idx.kospi_ma60_pct >= 0:
        score += 1.5

    # 양대 지수 동조성 (0~4)
    if idx.kospi_change_pct is not None and idx.kosdaq_change_pct is not None:
        both_positive = idx.kospi_change_pct > 0 and idx.kosdaq_change_pct > 0
        both_negative = idx.kospi_change_pct < 0 and idx.kosdaq_change_pct < 0
        if both_positive:
            score += 4.0
        elif both_negative:
            score += 0.0
        else:
            score += 2.0

    return min(25.0, max(0.0, score))


def _compute_breadth(inputs: MarketRegimeInputs) -> float:
    """Market Breadth Score (0~20)

    상승/하락 종목 비율 기반.
    """
    bd = inputs.breadth
    score = 0.0

    # 상승/하락 비율 (0~12)
    if bd.advance_count is not None and bd.decline_count is not None:
        total = bd.advance_count + bd.decline_count + (bd.unchanged_count or 0)
        if total > 0:
            advance_ratio = bd.advance_count / total
            if advance_ratio >= 0.7:
                score += 12.0
            elif advance_ratio >= 0.55:
                score += 8.0
            elif advance_ratio >= 0.45:
                score += 5.0
            elif advance_ratio >= 0.35:
                score += 2.0

    # 업종 확산 (0~8)
    if bd.advance_sector_count is not None and bd.total_sector_count is not None and bd.total_sector_count > 0:
        sector_ratio = bd.advance_sector_count / bd.total_sector_count
        if sector_ratio >= 0.7:
            score += 8.0
        elif sector_ratio >= 0.55:
            score += 5.0
        elif sector_ratio >= 0.4:
            score += 3.0
        elif sector_ratio >= 0.3:
            score += 1.0

    return min(20.0, max(0.0, score))


def _compute_momentum(inputs: MarketRegimeInputs) -> float:
    """Market Momentum Score (0~15)

    단기 모멘텀, 거래량 확산 기반.
    """
    mm = inputs.momentum
    score = 0.0

    # 당일 모멘텀 (0~5)
    if mm.kospi_1d_momentum is not None:
        if mm.kospi_1d_momentum >= 1.5:
            score += 5.0
        elif mm.kospi_1d_momentum >= 0.5:
            score += 3.0
        elif mm.kospi_1d_momentum >= -0.5:
            score += 2.0
        elif mm.kospi_1d_momentum >= -1.0:
            score += 1.0

    # 5일 모멘텀 (0~4)
    if mm.kospi_5d_momentum is not None:
        if mm.kospi_5d_momentum >= 3.0:
            score += 4.0
        elif mm.kospi_5d_momentum >= 1.0:
            score += 3.0
        elif mm.kospi_5d_momentum >= -1.0:
            score += 2.0
        elif mm.kospi_5d_momentum >= -2.0:
            score += 1.0

    # 20일 모멘텀 (0~3)
    if mm.kospi_20d_momentum is not None:
        if mm.kospi_20d_momentum >= 5.0:
            score += 3.0
        elif mm.kospi_20d_momentum >= 2.0:
            score += 2.0
        elif mm.kospi_20d_momentum >= -2.0:
            score += 1.0

    # 거래량 확산 (0~3)
    if mm.high_volume_ratio is not None:
        if mm.high_volume_ratio >= 0.6:
            score += 3.0
        elif mm.high_volume_ratio >= 0.4:
            score += 2.0
        elif mm.high_volume_ratio >= 0.2:
            score += 1.0

    return min(15.0, max(0.0, score))


def _compute_volatility(inputs: MarketRegimeInputs) -> float:
    """Volatility Risk Score (0~15)

    변동성이 낮고 안정적일수록 높은 점수.
    """
    vl = inputs.volatility
    score = 12.0  # 기본 중립

    # 장중 변동폭 감점 (기본 12점에서 차감)
    if vl.intraday_range_pct is not None:
        if vl.intraday_range_pct >= 3.0:
            score -= 8.0
        elif vl.intraday_range_pct >= 2.0:
            score -= 5.0
        elif vl.intraday_range_pct >= 1.5:
            score -= 3.0
        elif vl.intraday_range_pct >= 1.0:
            score -= 1.0
        elif vl.intraday_range_pct < 0.5:
            score += 1.0

    # VI 발동 감점
    if vl.vi_triggered_count is not None:
        if vl.vi_triggered_count > 20:
            score -= 4.0
        elif vl.vi_triggered_count > 10:
            score -= 2.0
        elif vl.vi_triggered_count > 5:
            score -= 1.0

    # 급등락 혼재
    if vl.extreme_updown_mixed is True:
        score -= 3.0

    # 추세 일관성
    if vl.trend_consistency is not None:
        score += (vl.trend_consistency - 0.5) * 4

    return min(15.0, max(0.0, score))


def _compute_trading_value(inputs: MarketRegimeInputs) -> float:
    """Trading Value Score (0~10)

    거래대금 수준과 증가 추세 기반.
    """
    tv = inputs.trading_value
    score = 5.0  # 기본 중립

    # 거래대금 증감 (0~10)
    if tv.volume_change_pct is not None:
        if tv.volume_change_pct >= 30:
            score += 5.0
        elif tv.volume_change_pct >= 15:
            score += 3.0
        elif tv.volume_change_pct >= 5:
            score += 1.0
        elif tv.volume_change_pct <= -20:
            score -= 4.0
        elif tv.volume_change_pct <= -10:
            score -= 2.0
        elif tv.volume_change_pct <= -5:
            score -= 1.0

    # 상위 집중도 (집중도가 낮을수록 좋음)
    if tv.top_volume_concentration is not None:
        if tv.top_volume_concentration < 0.3:
            score += 1.0
        elif tv.top_volume_concentration > 0.7:
            score -= 1.0

    return min(10.0, max(0.0, score))


def _compute_sector_strength(inputs: MarketRegimeInputs) -> float:
    """Sector Strength Score (0~10)"""
    ss = inputs.sector_strength
    score = 5.0  # 기본 중립

    if ss.up_sector_ratio is not None:
        if ss.up_sector_ratio >= 0.7:
            score += 3.0
        elif ss.up_sector_ratio >= 0.55:
            score += 2.0
        elif ss.up_sector_ratio >= 0.4:
            score += 1.0
        elif ss.up_sector_ratio < 0.3:
            score -= 2.0

    if ss.leading_sector_strength is not None:
        score += ss.leading_sector_strength * 2

    return min(10.0, max(0.0, score))


def _compute_foreign_flow(inputs: MarketRegimeInputs) -> float:
    """Foreign/Institution Flow Score (0~5)

    비중은 낮게 유지.
    """
    ff = inputs.foreign_flow
    score = 2.5  # 기본

    if ff.foreign_net_buy is not None:
        if ff.foreign_net_buy > 0:
            score += 1.5
        else:
            score -= 1.0

    if ff.institution_net_buy is not None:
        if ff.institution_net_buy > 0:
            score += 1.0
        else:
            score -= 0.5

    return min(5.0, max(0.0, score))


def _compute_risk_penalty(inputs: MarketRegimeInputs) -> float:
    """Market Risk Penalty (0~40)

    위험 요소가 많을수록 높은 감점.
    """
    idx = inputs.index
    bd = inputs.breadth
    vl = inputs.volatility
    tv = inputs.trading_value
    penalty = 0.0

    # KOSPI/KOSDAQ 동반 급락 (0~10)
    if idx.kospi_change_pct is not None and idx.kosdaq_change_pct is not None:
        if idx.kospi_change_pct <= -2.0 and idx.kosdaq_change_pct <= -2.0:
            penalty += 10.0
        elif idx.kospi_change_pct <= -1.5 and idx.kosdaq_change_pct <= -1.5:
            penalty += 7.0
        elif idx.kospi_change_pct <= -1.0 and idx.kosdaq_change_pct <= -1.0:
            penalty += 4.0
        elif idx.kospi_change_pct <= -0.5 and idx.kosdaq_change_pct <= -0.5:
            penalty += 2.0

    # 하락 종목 과다 (0~8)
    if bd.advance_count is not None and bd.decline_count is not None:
        total = bd.advance_count + bd.decline_count + (bd.unchanged_count or 0)
        if total > 0:
            decline_ratio = bd.decline_count / total
            if decline_ratio >= 0.7:
                penalty += 8.0
            elif decline_ratio >= 0.55:
                penalty += 5.0
            elif decline_ratio >= 0.45:
                penalty += 3.0

    # VI 발동 급증 (0~6)
    if vl.vi_triggered_count is not None:
        if vl.vi_triggered_count > 30:
            penalty += 6.0
        elif vl.vi_triggered_count > 20:
            penalty += 4.0
        elif vl.vi_triggered_count > 10:
            penalty += 2.0

    # 거래대금 급감 (0~6)
    if tv.volume_change_pct is not None:
        if tv.volume_change_pct <= -30:
            penalty += 6.0
        elif tv.volume_change_pct <= -20:
            penalty += 4.0
        elif tv.volume_change_pct <= -10:
            penalty += 2.0

    # 장중 변동성 과다 (0~6)
    if vl.intraday_range_pct is not None:
        if vl.intraday_range_pct >= 3.0:
            penalty += 6.0
        elif vl.intraday_range_pct >= 2.0:
            penalty += 4.0
        elif vl.intraday_range_pct >= 1.5:
            penalty += 2.0

    # 급등락 혼재 (0~4)
    if vl.extreme_updown_mixed is True:
        penalty += 4.0

    return min(40.0, max(0.0, penalty))


def calculate(inputs: MarketRegimeInputs) -> MarketRegimeScore:
    """MarketRegimeInputs → MarketRegimeScore 계산

    Args:
        inputs: KIS API 기반 시장 평가 입력

    Returns:
        각 항목별 점수가 포함된 MarketRegimeScore
    """
    return MarketRegimeScore(
        index_trend_score=_compute_index_trend(inputs),
        market_breadth_score=_compute_breadth(inputs),
        market_momentum_score=_compute_momentum(inputs),
        volatility_risk_score=_compute_volatility(inputs),
        trading_value_score=_compute_trading_value(inputs),
        sector_strength_score=_compute_sector_strength(inputs),
        foreign_institution_flow_score=_compute_foreign_flow(inputs),
        market_risk_penalty=_compute_risk_penalty(inputs),
    )