"""Session event types — Phase 3 Audit Logging Engine 연결용"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class SessionEventType(str, Enum):
    """세션 관련 이벤트 타입

    Phase 3 Audit Logging Engine에서 사용할 이벤트 타입을 미리 정의한다.
    Phase 2에서는 이벤트 생성까지만 구현하고, 로깅/전송은 Phase 3에서 구현.
    """

    TRADING_DAY_CHECKED = "TRADING_DAY_CHECKED"
    """거래일 확인 완료"""

    MARKET_SESSION_EVALUATED = "MARKET_SESSION_EVALUATED"
    """장운영상태 평가 완료"""

    SESSION_STATE_CHANGED = "SESSION_STATE_CHANGED"
    """세션 상태 변경"""

    PRE_MARKET_STARTED = "PRE_MARKET_STARTED"
    """장전 동시호가 시작"""

    REGULAR_MARKET_STARTED = "REGULAR_MARKET_STARTED"
    """정규장 시작"""

    LATE_MARKET_STARTED = "LATE_MARKET_STARTED"
    """장마감 임박 구간 진입"""

    NEW_BUY_BLOCKED_BY_SESSION = "NEW_BUY_BLOCKED_BY_SESSION"
    """세션 정책에 의해 신규매수 차단"""

    MARKET_CLOSED = "MARKET_CLOSED"
    """장 종료"""

    AFTER_MARKET_SYNC_STARTED = "AFTER_MARKET_SYNC_STARTED"
    """장후 동기화 시작"""

    EOD_TRIGGERED_BY_SESSION = "EOD_TRIGGERED_BY_SESSION"
    """세션 정책에 의해 EOD 트리거"""

    SESSION_STATE_UNKNOWN = "SESSION_STATE_UNKNOWN"
    """세션 상태 불명 (API 실패 등)"""


@dataclass(frozen=True)
class SessionEvent:
    """세션 이벤트 레코드

    Phase 2에서는 생성까지만.
    Phase 3에서 로깅/전송 시 이 객체를 사용함.
    """

    event_type: SessionEventType
    session_state: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""

    @property
    def event_name(self) -> str:
        return self.event_type.value