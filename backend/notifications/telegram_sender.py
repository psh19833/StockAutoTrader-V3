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


class RealTelegramSender(TelegramSender):
    """실제 Telegram Bot API를 호출하는 Sender.

    .env에서 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID를 읽어 사용.
    token/chat_id 원문은 repr/log에 노출하지 않음.
    실패해도 예외를 발생시키지 않고 SendResult(success=False) 반환.
    """

    def __init__(self):
        import os
        self._token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    def send(self, event: TelegramEvent) -> SendResult:
        if not self._token or not self._chat_id:
            return SendResult(
                success=False,
                telegram_event=event,
                error_message="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set",
            )
        try:
            import urllib.request, json
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            body = json.dumps({
                "chat_id": self._chat_id,
                "text": event.formatted_message,
                "parse_mode": "HTML",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                return SendResult(
                    success=True,
                    telegram_event=event,
                    message_id=str(data["result"].get("message_id", "")),
                )
            return SendResult(
                success=False,
                telegram_event=event,
                error_message=data.get("description", "unknown error"),
            )
        except Exception as e:
            return SendResult(
                success=False,
                telegram_event=event,
                error_message=str(e)[:200],
            )

    def __repr__(self) -> str:
        return "RealTelegramSender(token=***, chat_id=***)"