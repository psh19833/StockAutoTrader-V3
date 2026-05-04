"""RiskDecision — Risk Engine 최종 판단 결과

RiskDecision APPROVED도 실제 주문 실행이 아니다.
Live Order Gate를 통과해야 실제 주문으로 전환된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from risk.risk_types import RiskDecisionStatus


@dataclass(frozen=True)
class RiskDecision:
    """Risk Engine 판단 결과

    Attributes:
        risk_decision_id: 판단 고유 ID
        signal_id: 연결된 StrategySignal ID
        correlation_id: 추적용 correlation ID
        symbol: 종목 코드
        side: BUY / SELL
        status: APPROVED / REJECTED / BLOCKED
        allowed: 주문 허용 여부
        reason_code: 판단 사유 코드
        reason_text: 판단 사유 설명
        checked_items: 검증 완료된 항목
        failed_items: 실패한 검증 항목
        market_regime: 판단 시점 시장 상태
        session_state: 판단 시점 세션 상태
        requested_amount: 요청 금액
        created_at: 판단 시각
    """
    risk_decision_id: str
    signal_id: str
    correlation_id: str
    symbol: str
    side: str
    status: RiskDecisionStatus
    allowed: bool
    reason_code: str
    reason_text: str
    checked_items: tuple[str, ...] = ()
    failed_items: tuple[str, ...] = ()
    market_regime: str = ""
    session_state: str = ""
    requested_amount: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
