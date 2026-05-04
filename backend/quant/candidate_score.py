"""Quant Candidate Score and Decision models"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuantDecision(str, Enum):
    """Quant 후보 최종 판단"""
    PASS = "PASS"
    WATCH = "WATCH"
    REJECT = "REJECT"


@dataclass(frozen=True)
class QuantCandidateScore:
    """Quant 후보 점수

    Scanner 후보를 정량적으로 평가한 결과.
    PASS는 매수 신호가 아니다 — Strategy Engine에 넘길 수 있는 후보라는 의미.

    Attributes:
        symbol: 종목 코드
        scanner_type: Scanner Type
        scan_run_id: 연결된 스캔 실행 ID
        evaluation_id: 평가 ID
        liquidity_score: 유동성 점수
        spread_score: 호가 스프레드 점수
        volume_score: 거래량 점수
        momentum_score: 모멘텀 점수
        trend_score: 추세 점수
        orderbook_score: 호가창 점수
        volatility_safety_score: 변동성 안전 점수
        market_regime_adjustment: 시장 상태 보정값
        symbol_risk_penalty: 종목 리스크 패널티
        final_score: 최종 점수 (base + adjustment - penalty)
        decision: 최종 판단
        reasons: 판단 근거
        surge_velocity_score: (RAPID_SURGE) 급등 속도 점수
        volume_burst_score: (RAPID_SURGE) 거래량 폭증 점수
        intraday_high_proximity_score: (RAPID_SURGE) 당일 고점 근접 점수
        vi_proximity_penalty: (RAPID_SURGE) VI 근접 패널티
        pullback_failure_penalty: (RAPID_SURGE) 눌림 실패 패널티
        prior_strength_score: (PULLBACK_REBOUND) 이전 상승 강도 점수
        pullback_depth_score: (PULLBACK_REBOUND) 눌림 깊이 점수
        rebound_confirmation_score: (PULLBACK_REBOUND) 반등 확인 점수
        support_holding_score: (PULLBACK_REBOUND) 지지 유지 점수
        source_endpoints: 데이터 출처
        data_quality_warnings: 데이터 품질 경고
    """
    # 식별
    symbol: str
    scanner_type: str
    scan_run_id: str
    evaluation_id: str

    # 공통 점수
    liquidity_score: float = 0.0
    spread_score: float = 0.0
    volume_score: float = 0.0
    momentum_score: float = 0.0
    trend_score: float = 0.0
    orderbook_score: float = 0.0
    volatility_safety_score: float = 0.0
    market_regime_adjustment: float = 0.0
    symbol_risk_penalty: float = 0.0

    # 최종
    final_score: float = 0.0
    decision: QuantDecision = QuantDecision.REJECT
    reasons: tuple[str, ...] = ()

    # RAPID_SURGE 전용
    surge_velocity_score: float = 0.0
    volume_burst_score: float = 0.0
    intraday_high_proximity_score: float = 0.0
    vi_proximity_penalty: float = 0.0
    pullback_failure_penalty: float = 0.0

    # PULLBACK_REBOUND 전용
    prior_strength_score: float = 0.0
    pullback_depth_score: float = 0.0
    rebound_confirmation_score: float = 0.0
    support_holding_score: float = 0.0

    # 메타데이터
    source_endpoints: tuple[str, ...] = ()
    data_quality_warnings: tuple[str, ...] = ()