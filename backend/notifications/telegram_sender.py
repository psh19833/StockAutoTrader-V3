"""TelegramSender — Telegram 메시지 전송 인터페이스

실제 Telegram HTTP 호출 없이 인터페이스만 정의하고,
InMemoryTelegramSender로 테스트 가능하게 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from notifications.telegram_event import TelegramEvent


@dataclass(frozen=True)
class SendResult:
    """전송 결과"""
    success: bool
    telegram_event: TelegramEvent
    error_message: str | None = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_id: str | None = None


class TelegramSender:
    """TelegramSender 인터페이스

    Concrete 구현체는 send()를 구현한다.
    실패해도 예외를 발생시키지 않고 SendResult(success=False)를 반환한다.
    """
    def send(self, event: TelegramEvent) -> SendResult:
        """Telegram 메시지 전송

        Args:
            event: 전송할 TelegramEvent

        Returns:
            SendResult — 실패해도 예외 대신 success=False 반환
        """
        raise NotImplementedError


class InMemoryTelegramSender(TelegramSender):
    """메모리 기반 Telegram Sender (테스트용)

    실제 API 호출 없이 전송 결과를 메모리에 저장한다.
    """

    def __init__(self, should_fail: bool = False):
        self._sent_events: list[TelegramEvent] = []
        self._should_fail = should_fail

    def send(self, event: TelegramEvent) -> SendResult:
        """메모리에 저장하고 SendResult 반환"""
        if self._should_fail:
            return SendResult(
                success=False,
                telegram_event=event,
                error_message="Simulated send failure",
            )
        self._sent_events.append(event)
        return SendResult(
            success=True,
            telegram_event=event,
        )

    @property
    def sent_events(self) -> list[TelegramEvent]:
        """전송된 이벤트 목록"""
        return list(self._sent_events)

    @property
    def sent_count(self) -> int:
        return len(self._sent_events)

    def clear(self) -> None:
        self._sent_events.clear()