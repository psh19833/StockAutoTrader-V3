"""AuditEvent — SAT3 Audit Logging Engine의 핵심 이벤트 모델"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

SeverityLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AuditEventType(str, Enum):
    """SAT3 Audit Event Type 목록

    모든 핵심 판단과 이벤트를 추적 가능한 타입.
    사고 추적, 판단 근거 보존, 성과 분석을 위한 이벤트 분류.
    """
    # ── 서버 ──
    SERVER_STARTED = "SERVER_STARTED"
    SERVER_STOPPED = "SERVER_STOPPED"

    # ── KIS API ──
    KIS_API_CALLED = "KIS_API_CALLED"
    KIS_API_FAILED = "KIS_API_FAILED"

    # ── 시장/세션 ──
    TRADING_DAY_CHECKED = "TRADING_DAY_CHECKED"
    MARKET_SESSION_EVALUATED = "MARKET_SESSION_EVALUATED"
    SESSION_STATE_CHANGED = "SESSION_STATE_CHANGED"
    NEW_BUY_BLOCKED_BY_SESSION = "NEW_BUY_BLOCKED_BY_SESSION"
    SESSION_STATE_UNKNOWN = "SESSION_STATE_UNKNOWN"

    # ── 시장 국면 ──
    MARKET_REGIME_EVALUATED = "MARKET_REGIME_EVALUATED"

    # ── 스캐너 ──
    SCAN_STARTED = "SCAN_STARTED"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    CANDIDATE_DISCOVERED = "CANDIDATE_DISCOVERED"
    CANDIDATE_EXCLUDED = "CANDIDATE_EXCLUDED"

    # ── 정량평가 ──
    QUANT_EVALUATED = "QUANT_EVALUATED"

    # ── 전략 ──
    STRATEGY_SIGNAL_CREATED = "STRATEGY_SIGNAL_CREATED"

    # ── 리스크 ──
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"

    # ── 주문 ──
    ORDER_INTENT_APPROVED = "ORDER_INTENT_APPROVED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FAILED = "ORDER_FAILED"
    ORDER_CANCELLED = "ORDER_CANCELLED"

    # ── 체결 ──
    FILL_CONFIRMED = "FILL_CONFIRMED"

    # ── 포지션 ──
    POSITION_SYNCED = "POSITION_SYNCED"

    # ── EOD ──
    EOD_REPORT_CREATED = "EOD_REPORT_CREATED"

    # ── 비상정지 ──
    EMERGENCY_STOP_ACTIVATED = "EMERGENCY_STOP_ACTIVATED"
    EMERGENCY_STOP_RELEASED = "EMERGENCY_STOP_RELEASED"


@dataclass(frozen=True)
class AuditEvent:
    """Audit Event

    SAT3의 모든 핵심 판단과 이벤트를 기록하는 단위.
    모든 필드는 불변(immutable)이며, 직렬화 가능해야 함.

    Attributes:
        event_id: 고유 이벤트 ID (UUID v4)
        event_type: AuditEventType 값
        event_time: 이벤트 발생 시각 (UTC)
        severity: 로그 심각도
        correlation_id: 거래 흐름 연결 ID (선택)
        trading_day: 거래일 날짜 (선택)
        symbol: 종목 코드 (선택)
        strategy_name: 전략명 (선택)
        payload: 이벤트별 추가 데이터
        source: 이벤트 발생 출처 (모듈명)
        created_at: AuditEvent 생성 시각
    """
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_type: str = ""
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: SeverityLevel = "INFO"
    correlation_id: str | None = None
    trading_day: date | None = None
    symbol: str | None = None
    strategy_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# fake fill / simulated order event type 미포함 확인용 상수
FORBIDDEN_EVENT_TYPES: frozenset[str] = frozenset({
    "FAKE_FILL_CONFIRMED",
    "SIMULATED_ORDER_SUBMITTED",
    "SIMULATED_FILL_CONFIRMED",
    "ORDER_SIMULATED",
})