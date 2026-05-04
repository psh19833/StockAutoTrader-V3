"""MarketRegimePolicy — 점수로 상태 분류하고 정책 결정

분류 기준:
  - BULL:    70점 이상
  - NEUTRAL: 40~69점
  - BEAR:    0~39점
  - UNKNOWN: API 실패, source 검증 실패, 핵심 데이터 부족

시장 상태별 정책:
  BULL:     adjustment +5~+10, allow_new_buy=True,  min_score=기본값
  NEUTRAL:  adjustment 0,      allow_new_buy=True,  min_score=기본값
  BEAR:     adjustment -15~-30, allow_new_buy=False, min_score=999
  UNKNOWN:  adjustment -30,     allow_new_buy=False, min_score=999

Risk Penalty 정책:
  penalty >= 25 → 기준 강화
  penalty >= 35 → 신규매수 전체 차단
"""
from __future__ import annotations

from market_regime.regime_state import MarketRegime, BULL_THRESHOLD, NEUTRAL_LOWER
from market_regime.regime_score import MarketRegimeScore
from market_regime.regime_inputs import MarketRegimeInputs
from market_regime.regime_result import MarketRegimeResult

DEFAULT_MIN_SCORE = 50.0  # 기본 최소 후보 점수


def classify_regime(total_score: float) -> MarketRegime:
    """점수로 시장 상태 분류

    Args:
        total_score: 0~100 정규화된 시장 점수

    Returns:
        MarketRegime 분류 결과
    """
    if total_score >= BULL_THRESHOLD:
        return MarketRegime.BULL
    elif total_score >= NEUTRAL_LOWER:
        return MarketRegime.NEUTRAL
    else:
        return MarketRegime.BEAR


def determine_policy(regime: MarketRegime, score: MarketRegimeScore
                     ) -> tuple[float, bool, float, tuple[str, ...]]:
    """시장 상태별 정책 결정

    Returns:
        (candidate_score_adjustment, allow_new_buy, min_candidate_score_required, reasons)
    """
    penalty = score.market_risk_penalty
    reasons: list[str] = []
    warnings: list[str] = []

    # Risk Penalty 우선 확인
    if penalty >= 35:
        reasons.append(f"Market Risk Penalty={penalty:.1f} >= 35: new buy blocked")
        return (-30.0, False, 999.0, tuple(reasons))
    elif penalty >= 25:
        reasons.append(f"Market Risk Penalty={penalty:.1f} >= 25: criteria tightened")
        # Penalty가 높으면 정책을 한 단계 강화
        if regime == MarketRegime.BULL:
            regime = MarketRegime.NEUTRAL
            reasons.append("Penalty downgraded BULL to NEUTRAL")
        elif regime == MarketRegime.NEUTRAL:
            regime = MarketRegime.BEAR
            reasons.append("Penalty downgraded NEUTRAL to BEAR")

    if regime == MarketRegime.BULL:
        adjustment = 7.5  # +5~+10 중간값
        return (adjustment, True, DEFAULT_MIN_SCORE,
                tuple(reasons + [f"BULL regime: candidate score adjustment +{adjustment:.1f}"]))

    elif regime == MarketRegime.NEUTRAL:
        return (0.0, True, DEFAULT_MIN_SCORE,
                tuple(reasons + ["NEUTRAL regime: no adjustment"]))

    elif regime == MarketRegime.BEAR:
        adjustment = -20.0
        return (adjustment, False, 999.0,
                tuple(reasons + [f"BEAR regime: new buy blocked, adjustment {adjustment:.0f}"]))

    else:  # UNKNOWN
        return (-30.0, False, 999.0,
                tuple(reasons + ["UNKNOWN regime: new buy blocked"]))


def evaluate(inputs: MarketRegimeInputs, score: MarketRegimeScore) -> MarketRegimeResult:
    """MarketRegimeInputs + MarketRegimeScore → MarketRegimeResult

    Args:
        inputs: 시장 평가 입력값 (source 검증 포함)
        score: 계산된 세부 점수

    Returns:
        MarketRegimeResult
    """
    data_quality_warnings = inputs.validate()

    # 데이터 품질 확인 — 핵심 데이터 부족 시 UNKNOWN
    has_core_data = (
        inputs.index.kospi_current is not None
        and inputs.index.kosdaq_current is not None
        and inputs.breadth.advance_count is not None
        and inputs.breadth.decline_count is not None
        and inputs.momentum.kospi_1d_momentum is not None
    )
    source_valid = inputs.source.upper() == "KIS_API"

    if not source_valid:
        data_quality_warnings.append(f"Invalid source: {inputs.source}")

    if not source_valid or not has_core_data:
        regime = MarketRegime.UNKNOWN
        total_score = 0.0
        if not has_core_data:
            data_quality_warnings.append("Core market data missing")
    else:
        total_score = score.total_score
        regime = classify_regime(total_score)

    adjustment, allow_new_buy, min_score, reasons = determine_policy(regime, score)

    return MarketRegimeResult(
        regime=regime,
        score=score,
        total_score=total_score,
        candidate_score_adjustment=adjustment,
        allow_new_buy=allow_new_buy,
        min_candidate_score_required=min_score,
        reasons=reasons,
        source_endpoints=inputs.source_endpoints,
        data_quality_warnings=tuple(data_quality_warnings),
    )