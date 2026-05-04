"""StrategySignal — 진입/청산 의도 표현

StrategySignal은 실제 주문이 아니다.
StrategySignal은 Strategy Engine이 생성하고 Risk Engine이 검증한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from strategy.strategy_types import StrategyType


@dataclass(frozen=True)
class StrategySignal:
    """전략 신호

    Attributes:
        signal_id: 신호 고유 ID
        correlation_id: 추적용 correlation ID
        symbol: 종목 코드
        side: BUY / SELL
        strategy_type: 전략 타입
        confidence: 신뢰도 (0.0 ~ 1.0)
        source_quant_id: 연결된 Quant 평가 ID
        scanner_type: 연결된 Scanner Type
        market_regime: 신호 생성 시점 시장 상태
        expected_entry_price: 예상 진입가 (None 가능)
        suggested_stop_loss_rate: 제안 손절률
        suggested_take_profit_rate: 제안 익절률
        suggested_time_exit_minutes: 제안 시간청산 (분)
        evidence: 판단 근거 튜플
        created_at: 생성 시각
        source_endpoints: 데이터 출처
        data_quality_warnings: 데이터 품질 경고
    """
    signal_id: str
    correlation_id: str
    symbol: str
    side: str  # BUY / SELL
    strategy_type: StrategyType
    source_quant_id: str
    scanner_type: str
    market_regime: str

    confidence: float = 0.0
    expected_entry_price: float | None = None
    suggested_stop_loss_rate: float = 0.0
    suggested_take_profit_rate: float = 0.0
    suggested_time_exit_minutes: int = 0
    evidence: tuple[str, ...] = ()
    source_endpoints: tuple[str, ...] = ()
    data_quality_warnings: tuple[str, ...] = ()
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
