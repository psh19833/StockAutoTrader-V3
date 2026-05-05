"""Strategy Evaluator — QuantCandidateScore → StrategySignal

Quant PASS → evaluate_entry() → StrategySignal (BUY)
보유 종목 → evaluate_exit() → StrategySignal (SELL)

Signal은 주문이 아니다. Risk Engine 승인 전까지 주문으로 전환되지 않는다.

핵심 안전 원칙:
  - data_quality_warnings가 있으면 Quant PASS라도 StrategySignal 생성 금지.
  - Quant REJECT/WATCH → StrategySignal 생성 금지.
"""
from __future__ import annotations

import uuid
from typing import Any

from quant.candidate_score import QuantCandidateScore, QuantDecision
from scanner.scanner_types import ScannerType
from market_regime.regime_result import MarketRegimeResult
from strategy.strategy_types import StrategyType
from strategy.signal import StrategySignal
from strategy.strategy_policy import get_policy_for_regime


# Scanner Type → Strategy Type 매핑
_SCANNER_TO_STRATEGY = {
    ScannerType.RAPID_SURGE: StrategyType.RAPID_SURGE_SCALPING,
    ScannerType.LIQUIDITY_MOMENTUM: StrategyType.LIQUIDITY_MOMENTUM_FOLLOW,
    ScannerType.BREAKOUT: StrategyType.BREAKOUT_FOLLOW,
    ScannerType.PULLBACK_REBOUND: StrategyType.PULLBACK_REBOUND,
}


def map_scanner_to_strategy(scanner_type: ScannerType) -> StrategyType:
    """Scanner Type → Strategy Type 매핑"""
    return _SCANNER_TO_STRATEGY[scanner_type]


def compute_confidence(
    final_score: float,
    decision: QuantDecision,
    liquidity_score: float,
    spread_score: float,
    momentum_score: float,
    symbol_risk_penalty: float,
) -> float:
    """신뢰도 계산 (0.0 ~ 1.0)

    Quant REJECT/WATCH → confidence = 0
    Quant PASS → 점수 기반 신뢰도 계산
    """
    if decision != QuantDecision.PASS:
        return 0.0

    # 기본 신뢰도: final_score / 100 (0~1)
    base = min(final_score / 100.0, 1.0)

    # 품질 가중치: 유동성 + 스프레드 + 모멘텀 (평균 0~10)
    quality = (liquidity_score + spread_score + momentum_score) / 30.0

    # 리스크 감점
    risk_discount = min(symbol_risk_penalty / 10.0, 0.5)

    confidence = (base * 0.5 + quality * 0.5) - risk_discount
    return max(0.0, min(1.0, confidence))


def evaluate_entry(
    score: QuantCandidateScore,
    regime_result: MarketRegimeResult,
) -> StrategySignal | None:
    """Quant PASS 후보 → 진입 신호 생성

    Args:
        score: Quant 평가 결과
        regime_result: 시장 상태

    Returns:
        StrategySignal (BUY), 또는 신호 생성 불가 시 None
    """
    # Quant REJECT/WATCH → 신호 생성 금지
    if score.decision != QuantDecision.PASS:
        return None

    # STEP 11: data_quality_warnings가 있으면 신호 생성 금지
    # data_quality_warnings는 evidence에 남기지 않고, 신호 생성 자체를 막는다
    if score.data_quality_warnings:
        return None

    # Market Regime 차단
    if not regime_result.allow_new_buy:
        return None

    # 전략 정책 확인
    stype = map_scanner_to_strategy(
        ScannerType(score.scanner_type) if isinstance(score.scanner_type, str)
        else score.scanner_type
    )
    policy = get_policy_for_regime(regime_result.regime.value)
    if not policy.is_enabled(stype):
        return None

    # 신뢰도 계산
    confidence = compute_confidence(
        final_score=score.final_score,
        decision=score.decision,
        liquidity_score=score.liquidity_score,
        spread_score=score.spread_score,
        momentum_score=score.momentum_score,
        symbol_risk_penalty=score.symbol_risk_penalty,
    )

    # 최소 신뢰도 확인
    if confidence < policy.min_confidence(stype):
        return None

    return StrategySignal(
        signal_id=f"sig_{uuid.uuid4().hex[:12]}",
        correlation_id=score.evaluation_id,
        symbol=score.symbol,
        side="BUY",
        strategy_type=stype,
        confidence=round(confidence, 4),
        source_quant_id=score.evaluation_id,
        scanner_type=score.scanner_type,
        market_regime=regime_result.regime.value,
        evidence=score.reasons,
        source_endpoints=score.source_endpoints,
        data_quality_warnings=score.data_quality_warnings,
    )


def evaluate_exit(
    symbol: str,
    strategy_type: StrategyType,
    reason: str,
    market_regime: str,
    source_quant_id: str = "",
) -> StrategySignal:
    """청산 신호 생성

    보유 종목에 대한 청산 의도를 생성한다.
    """
    return StrategySignal(
        signal_id=f"sig_{uuid.uuid4().hex[:12]}",
        correlation_id=f"exit_{uuid.uuid4().hex[:8]}",
        symbol=symbol,
        side="SELL",
        strategy_type=strategy_type,
        confidence=1.0,
        source_quant_id=source_quant_id,
        scanner_type="FAST_EXIT",
        market_regime=market_regime,
        evidence=(reason,),
    )
