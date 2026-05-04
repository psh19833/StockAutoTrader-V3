"""TelegramEvent — Telegram 알림 요청 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NotificationSeverity(str, Enum):
    """알림 심각도 (Telegram 전송 기준)"""
    LOW = "LOW"              # 참고용 (EOD 리포트 등)
    NORMAL = "NORMAL"        # 일반 알림 (세션 변경, 스캔 완료 등)
    HIGH = "HIGH"            # 중요 알림 (주문, 체결, 리스크 판단)
    CRITICAL = "CRITICAL"    # 긴급 알림 (비상정지, API 실패 연속 등)


class TelegramEventType(str, Enum):
    """Telegram으로 전송 가능한 이벤트 타입"""
    # 서버
    SERVER_STARTED = "SERVER_STARTED"
    SERVER_STOPPED = "SERVER_STOPPED"
    # 세션
    TRADING_DAY_CHECKED = "TRADING_DAY_CHECKED"
    SESSION_STATE_CHANGED = "SESSION_STATE_CHANGED"
    SESSION_STATE_UNKNOWN = "SESSION_STATE_UNKNOWN"
    NEW_BUY_BLOCKED_BY_SESSION = "NEW_BUY_BLOCKED_BY_SESSION"
    # 시장 국면
    MARKET_REGIME_EVALUATED = "MARKET_REGIME_EVALUATED"
    # 스캐너
    SCAN_COMPLETED = "SCAN_COMPLETED"
    CANDIDATE_DISCOVERED = "CANDIDATE_DISCOVERED"
    # 전략
    STRATEGY_SIGNAL_CREATED = "STRATEGY_SIGNAL_CREATED"
    # 리스크
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    # 주문
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FAILED = "ORDER_FAILED"
    # 체결
    FILL_CONFIRMED = "FILL_CONFIRMED"
    # 포지션
    POSITION_SYNCED = "POSITION_SYNCED"
    # EOD
    EOD_REPORT_CREATED = "EOD_REPORT_CREATED"
    # 비상
    EMERGENCY_STOP_ACTIVATED = "EMERGENCY_STOP_ACTIVATED"
    EMERGENCY_STOP_RELEASED = "EMERGENCY_STOP_RELEASED"
    # KIS
    KIS_API_FAILED = "KIS_API_FAILED"


# 이벤트 타입별 기본 심각도 매핑
DEFAULT_SEVERITY_MAP: dict[str, NotificationSeverity] = {
    TelegramEventType.SERVER_STARTED.value: NotificationSeverity.NORMAL,
    TelegramEventType.SERVER_STOPPED.value: NotificationSeverity.HIGH,
    TelegramEventType.TRADING_DAY_CHECKED.value: NotificationSeverity.LOW,
    TelegramEventType.SESSION_STATE_CHANGED.value: NotificationSeverity.NORMAL,
    TelegramEventType.SESSION_STATE_UNKNOWN.value: NotificationSeverity.CRITICAL,
    TelegramEventType.NEW_BUY_BLOCKED_BY_SESSION.value: NotificationSeverity.HIGH,
    TelegramEventType.MARKET_REGIME_EVALUATED.value: NotificationSeverity.NORMAL,
    TelegramEventType.SCAN_COMPLETED.value: NotificationSeverity.NORMAL,
    TelegramEventType.CANDIDATE_DISCOVERED.value: NotificationSeverity.NORMAL,
    TelegramEventType.STRATEGY_SIGNAL_CREATED.value: NotificationSeverity.HIGH,
    TelegramEventType.RISK_APPROVED.value: NotificationSeverity.NORMAL,
    TelegramEventType.RISK_REJECTED.value: NotificationSeverity.HIGH,
    TelegramEventType.ORDER_SUBMITTED.value: NotificationSeverity.HIGH,
    TelegramEventType.ORDER_FAILED.value: NotificationSeverity.CRITICAL,
    TelegramEventType.FILL_CONFIRMED.value: NotificationSeverity.HIGH,
    TelegramEventType.POSITION_SYNCED.value: NotificationSeverity.LOW,
    TelegramEventType.EOD_REPORT_CREATED.value: NotificationSeverity.NORMAL,
    TelegramEventType.EMERGENCY_STOP_ACTIVATED.value: NotificationSeverity.CRITICAL,
    TelegramEventType.EMERGENCY_STOP_RELEASED.value: NotificationSeverity.HIGH,
    TelegramEventType.KIS_API_FAILED.value: NotificationSeverity.HIGH,
}


@dataclass(frozen=True)
class TelegramEvent:
    """Telegram 알림 요청 데이터

    AuditEvent → Formatter → TelegramEvent → Sender → Telegram API
    """
    event_type: str                                    # TelegramEventType value
    title: str                                         # 메시지 제목 (bold 처리)
    body: str                                          # 메시지 본문
    notification_severity: NotificationSeverity        # 알림 심각도
    correlation_id: str | None = None                  # 연결된 거래 흐름 ID
    source_audit_event_id: str | None = None           # 원본 AuditEvent ID
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def formatted_message(self) -> str:
        """Telegram 전송용 완전한 문자열 메시지"""
        level_icon = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "NORMAL": "ℹ️",
            "LOW": "🔹",
        }.get(self.notification_severity.value, "📋")
        return f"{level_icon} *{self.title}*\n{self.body}"