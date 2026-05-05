"""TelegramNotifier — AuditEvent → Telegram 알림 Orchestrator

Pipeline:
  AuditEvent → Policy(is_allowed?) → Formatter(→ TelegramEvent) → Sender(→ SendResult)

어떤 단계에서 실패해도 예외가 매매 흐름을 중단하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from audit_logging.audit_event import AuditEvent
from notifications.telegram_event import TelegramEvent
from notifications.telegram_formatter import format_audit_event
from notifications.telegram_policy import (
    TelegramNotificationPolicy,
    ThrottlingTracker,
    ThrottlingPolicy,
)
from notifications.telegram_sender import TelegramSender, SendResult


@dataclass
class TelegramNotifier:
    """Telegram 알림 Orchestrator

    AuditEvent를 입력받아 Policy → Formatter → Sender 파이프라인 실행.
    """
    policy: TelegramNotificationPolicy = field(
        default_factory=TelegramNotificationPolicy
    )
    sender: TelegramSender | None = None
    throttling_tracker: ThrottlingTracker = field(
        default_factory=ThrottlingTracker
    )

    def notify(self, event: AuditEvent) -> SendResult | None:
        """AuditEvent → Telegram 알림 전송

        Args:
            event: 알림을 보낼 AuditEvent

        Returns:
            전송 성공/실패 결과. Policy에서 차단되면 None 반환.
            예외가 발생해도 None 반환 (safe failure)
        """
        try:
            if self.sender is None:
                return None

            # Step 1: Policy 확인
            if not self.policy.is_allowed(event):
                return None

            # Step 2: Throttling 확인 (비상정지는 bypass)
            is_emergency = event.event_type in (
                "EMERGENCY_STOP_ACTIVATED", "EMERGENCY_STOP_RELEASED",
                "WS_DISCONNECTED",
            )
            if not is_emergency:
                throttle_policy = self.policy.get_throttling_policy(event.event_type)
                if throttle_policy is not None:
                    if not self.throttling_tracker.can_send(event.event_type, throttle_policy):
                        return None

            # Step 3: Formatter 변환
            try:
                telegram_event = format_audit_event(event)
            except ValueError:
                # 지원하지 않는 event_type → 조용히 무시
                return None

            # Step 4: Sender 전송
            result = self.sender.send(telegram_event)

            # Step 5: Throttling 기록
            if result.success and throttle_policy is not None:
                self.throttling_tracker.record_send(event.event_type)

            return result

        except Exception:
            # 어떤 예외도 매매 흐름을 중단하지 않음
            return None