"""WebSocket → AuditEvent bridge.

WebSocket으로 수신한 실시간 메시지와 연결 상태 변화를
SAT3 AuditEvent로 변환한다.

이 브릿지는 조회/관제용이며, 자동 주문 실행을 유발하지 않는다.
Telegram 전송은 이번 단계에서 구현하지 않고, 기존 AuditEvent
파이프라인을 통해 나중에 연결 가능하게 구조만 제공한다.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from audit_logging.audit_event import AuditEvent, AuditEventType
from kis.ws_models import (
    WebSocketMessageBase,
    RealtimeTradeTick,
    RealtimeOrderBook,
    RealtimeFillNotice,
    RealtimeMarketStatus,
    RealtimeExpectedExecution,
)

# ── Event type mapping ───────────────────────────────────────────────────────

_MESSAGE_TYPE_MAP = {
    "H0STCNT0": "WS_TRADE_TICK_RECEIVED",
    "H0STASP0": "WS_ORDER_BOOK_RECEIVED",
    "H0STCNI0": "WS_FILL_NOTICE_RECEIVED",
    "H0STMKO0": "WS_MARKET_STATUS_RECEIVED",
    "H0STANC0": "WS_EXPECTED_EXECUTION_RECEIVED",
}

_WS_EVENT_TYPES: frozenset[str] = frozenset({
    "WS_CONNECTED",
    "WS_DISCONNECTED",
    "WS_RECONNECTING",
    "WS_TRADE_TICK_RECEIVED",
    "WS_ORDER_BOOK_RECEIVED",
    "WS_FILL_NOTICE_RECEIVED",
    "WS_MARKET_STATUS_RECEIVED",
    "WS_EXPECTED_EXECUTION_RECEIVED",
})


def is_ws_event_type(event_type: str) -> bool:
    """Check if an event type is WebSocket-related."""
    return event_type in _WS_EVENT_TYPES


def wsevent_to_audit(
    message: WebSocketMessageBase,
    trading_day: Optional[date] = None,
) -> AuditEvent:
    """Convert a WebSocket message to an AuditEvent.

    변환 원칙:
      - raw message 전체는 AuditEvent에 포함하지 않음
      - appkey/approval_key/secret 등은 절대 payload에 포함하지 않음
      - parsed_ok=False인 메시지는 WARNING severity
      - 데이터 필드는 최소한만 payload에 포함
    """
    event_type = _MESSAGE_TYPE_MAP.get(message.tr_id, "WS_TRADE_TICK_RECEIVED")

    # parsed_ok=False → warning severity
    severity = "WARNING" if not message.parsed_ok else "INFO"

    payload = {
        "tr_id": message.tr_id,
        "symbol": message.symbol,
        "parsed_ok": message.parsed_ok,
    }

    if message.data_quality_warnings:
        payload["data_quality_warnings"] = message.data_quality_warnings

    # Add type-specific fields (minimal set, no raw message)
    if isinstance(message, RealtimeTradeTick):
        if message.trade_price is not None:
            payload["trade_price"] = message.trade_price
        if message.trade_volume is not None:
            payload["trade_volume"] = message.trade_volume
    elif isinstance(message, RealtimeOrderBook):
        payload["ask_levels"] = len(message.ask_prices)
        payload["bid_levels"] = len(message.bid_prices)
    elif isinstance(message, RealtimeFillNotice):
        if message.fill_price is not None:
            payload["fill_price"] = message.fill_price
        if message.fill_volume is not None:
            payload["fill_volume"] = message.fill_volume
    elif isinstance(message, RealtimeMarketStatus):
        if message.market_status is not None:
            payload["market_status"] = message.market_status
        if message.market_session is not None:
            payload["market_session"] = message.market_session
    elif isinstance(message, RealtimeExpectedExecution):
        if message.expected_price is not None:
            payload["expected_price"] = message.expected_price
        if message.expected_volume is not None:
            payload["expected_volume"] = message.expected_volume

    return AuditEvent(
        event_type=event_type,
        event_time=message.received_at,
        severity=severity,
        symbol=message.symbol or None,
        payload=payload,
        source="KIS_API_WS",
        trading_day=trading_day,
    )


def _make_connection_event(
    event_type: str,
    payload: Optional[dict] = None,
    severity: str = "INFO",
) -> AuditEvent:
    """Create a WebSocket connection lifecycle AuditEvent."""
    return AuditEvent(
        event_type=event_type,
        event_time=datetime.now(timezone.utc),
        severity=severity,
        payload=payload or {},
        source="KIS_API_WS",
    )


class WsEventBridge:
    """WebSocket → AuditEvent 변환 브릿지.

    사용 예:
        bridge = WsEventBridge()
        # 연결 상태 변화
        event = bridge.on_connect()
        event = bridge.on_disconnect()
        event = bridge.on_reconnect(attempt=2)
        # 실시간 메시지
        event = bridge.on_message(trade_tick)
    """

    def on_message(self, message: WebSocketMessageBase,
                   trading_day: Optional[date] = None) -> AuditEvent:
        """Convert a real-time WebSocket message to AuditEvent.

        이 메서드는 자동 주문 실행을 유발하지 않는다.
        """
        return wsevent_to_audit(message, trading_day=trading_day)

    def on_connect(self) -> AuditEvent:
        """WebSocket 연결 성공 이벤트."""
        return _make_connection_event("WS_CONNECTED")

    def on_disconnect(self) -> AuditEvent:
        """WebSocket 연결 종료 이벤트."""
        return _make_connection_event("WS_DISCONNECTED")

    def on_reconnect(self, attempt: int) -> AuditEvent:
        """WebSocket 재연결 시도 이벤트."""
        return _make_connection_event(
            "WS_RECONNECTING",
            payload={"attempt": attempt},
            severity="WARNING",
        )
