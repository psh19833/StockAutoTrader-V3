"""TelegramNotificationPolicy — 어떤 AuditEvent를 Telegram으로 보낼지 결정

Alowlist / Blocklist / Severity 필터 / Throttling 정책을 지원한다.
실제 scheduler/timer 구현 없이 정책 객체만 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from audit_logging.audit_event import AuditEvent


# 기본 이벤트 알림 리스트 (Phase 3B 요구사항 기준)
DEFAULT_ALLOWED_EVENT_TYPES: frozenset[str] = frozenset({
    "SERVER_STARTED",
    "SERVER_STOPPED",
    "TRADING_DAY_CHECKED",
    "SESSION_STATE_CHANGED",
    "SESSION_STATE_UNKNOWN",
    "NEW_BUY_BLOCKED_BY_SESSION",
    "MARKET_REGIME_EVALUATED",
    "SCAN_COMPLETED",
    "CANDIDATE_DISCOVERED",
    "CANDIDATE_EXCLUDED",
    "QUANT_EVALUATED",
    "STRATEGY_SIGNAL_CREATED",
    "RISK_APPROVED",
    "RISK_REJECTED",
    "ORDER_SUBMITTED",
    "ORDER_FAILED",
    "FILL_CONFIRMED",
    "POSITION_SYNCED",
    "EOD_REPORT_CREATED",
    "EMERGENCY_STOP_ACTIVATED",
    "EMERGENCY_STOP_RELEASED",
    "KIS_API_FAILED",
})

# 기본 차단 이벤트 (너무 잦거나 중요도 낮은 이벤트)
DEFAULT_BLOCKED_EVENT_TYPES: frozenset[str] = frozenset({
    "KIS_API_CALLED",
    "SERVER_STARTED",
    "SCAN_STARTED",
})


@dataclass(frozen=True)
class ThrottlingPolicy:
    """알림 Throttling 정책 객체

    동일한 event_type이 지정된 시간(seconds) 내에
    최대 max_count회까지만 전송되도록 제한한다.
    """
    event_type: str
    max_count: int = 3          # seconds 내 최대 전송 횟수
    window_seconds: int = 60    # 시간 창 (초)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "max_count": self.max_count,
            "window_seconds": self.window_seconds,
        }


# 기본 Throttling 정책
DEFAULT_THROTTLING: tuple[ThrottlingPolicy, ...] = (
    ThrottlingPolicy(event_type="TRADING_DAY_CHECKED", max_count=1, window_seconds=600),
    ThrottlingPolicy(event_type="MARKET_SESSION_EVALUATED", max_count=1, window_seconds=300),
    ThrottlingPolicy(event_type="SCAN_COMPLETED", max_count=1, window_seconds=60),
    ThrottlingPolicy(event_type="QUANT_EVALUATED", max_count=1, window_seconds=60),
    ThrottlingPolicy(event_type="CANDIDATE_EXCLUDED", max_count=5, window_seconds=60),
)


@dataclass
class TelegramNotificationPolicy:
    """Telegram 알림 정책

    Attributes:
        allowed_event_types: 알림을 전송할 event_type 집합
        blocked_event_types: 알림을 차단할 event_type 집합
        min_severity: 최소 심각도 (이보다 낮은 이벤트는 차단)
        throttling: Throttling 정책 목록
    """
    allowed_event_types: frozenset[str] = DEFAULT_ALLOWED_EVENT_TYPES
    blocked_event_types: frozenset[str] = DEFAULT_BLOCKED_EVENT_TYPES
    min_severity: str = "LOW"
    throttling: tuple[ThrottlingPolicy, ...] = DEFAULT_THROTTLING

    def is_allowed(self, event: AuditEvent) -> bool:
        """이 AuditEvent를 Telegram으로 전송할지 결정"""
        # blocklist 우선 확인
        if event.event_type in self.blocked_event_types:
            return False
        # allowlist 확인
        if event.event_type not in self.allowed_event_types:
            return False
        # severity 확인 (INFO < WARNING < ERROR < CRITICAL)
        severity_order = {"DEBUG": 0, "LOW": 1, "NORMAL": 2, "INFO": 2,
                          "HIGH": 3, "WARNING": 3, "ERROR": 4, "CRITICAL": 5}
        event_sev = severity_order.get(event.severity.upper(), 1)
        min_sev = severity_order.get(self.min_severity.upper(), 1)
        return event_sev >= min_sev

    def get_throttling_policy(self, event_type: str) -> ThrottlingPolicy | None:
        """특정 event_type의 Throttling 정책 조회"""
        for tp in self.throttling:
            if tp.event_type == event_type:
                return tp
        return None


class ThrottlingTracker:
    """Throttling 상태 추적기

    동일 event_type의 최근 전송 시각을 기록하여
    ThrottlingPolicy에 따라 전송 가능 여부를 판단한다.
    실제 timer/scheduler를 사용하지 않고 객체 상태만 관리한다.
    """

    def __init__(self):
        self._history: dict[str, list[datetime]] = {}

    def can_send(self, event_type: str, policy: ThrottlingPolicy) -> bool:
        """Throttling 정책에 따라 전송 가능 여부 확인"""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=policy.window_seconds)

        # 해당 event_type의 히스토리 조회
        history = self._history.get(event_type, [])

        # 윈도우 내 이벤트만 필터
        recent = [t for t in history if t >= window_start]
        self._history[event_type] = recent

        return len(recent) < policy.max_count

    def record_send(self, event_type: str) -> None:
        """전송 기록"""
        if event_type not in self._history:
            self._history[event_type] = []
        self._history[event_type].append(datetime.now(timezone.utc))

    def clear(self) -> None:
        """히스토리 초기화 (테스트용)"""
        self._history.clear()