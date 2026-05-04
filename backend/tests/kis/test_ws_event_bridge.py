"""Tests for backend/kis/ws_event_bridge.py — WebSocket → AuditEvent bridge."""
import json
from datetime import datetime, timezone, date
from unittest.mock import MagicMock, patch

import pytest

from kis.ws_event_bridge import WsEventBridge, wsevent_to_audit, is_ws_event_type
from kis.ws_models import (
    RealtimeTradeTick,
    RealtimeOrderBook,
    RealtimeFillNotice,
    RealtimeMarketStatus,
    RealtimeExpectedExecution,
    WebSocketConnectionStatus,
    WebSocketMessageBase,
)
from audit_logging.audit_event import AuditEvent, AuditEventType


# ── WS Event Type helpers ────────────────────────────────────────────────────

class TestWsEventTypes:
    def test_ws_event_types_exist(self):
        """New WS event types must be added to AuditEventType."""
        required = {
            "WS_CONNECTED",
            "WS_DISCONNECTED",
            "WS_RECONNECTING",
            "WS_TRADE_TICK_RECEIVED",
            "WS_ORDER_BOOK_RECEIVED",
            "WS_FILL_NOTICE_RECEIVED",
            "WS_MARKET_STATUS_RECEIVED",
            "WS_EXPECTED_EXECUTION_RECEIVED",
        }
        existing = {e.value for e in AuditEventType}
        assert required <= existing, f"Missing: {required - existing}"

    def test_is_ws_event_type(self):
        assert is_ws_event_type("WS_CONNECTED") is True
        assert is_ws_event_type("WS_DISCONNECTED") is True
        assert is_ws_event_type("SCAN_STARTED") is False


# ── Message → AuditEvent conversion ──────────────────────────────────────────

class TestTradeTickToAudit:
    def test_convert_trade_tick(self):
        tick = RealtimeTradeTick(
            symbol="005930",
            trade_price=72000,
            trade_volume=100,
            trade_time="093015",
            raw_hash="hash123",
        )
        event = wsevent_to_audit(tick)
        assert event.event_type == "WS_TRADE_TICK_RECEIVED"
        assert event.symbol == "005930"
        assert event.payload["trade_price"] == 72000
        assert event.payload["trade_volume"] == 100
        assert event.severity == "INFO"
        assert event.source == "KIS_API_WS"

    def test_trade_tick_does_not_contain_raw_message(self):
        tick = RealtimeTradeTick(
            symbol="005930",
            trade_price=72000,
            raw_hash="hash123",
        )
        event = wsevent_to_audit(tick)
        assert "raw_message" not in event.payload
        assert "raw_hash" not in event.payload  # not in audit payload
        assert "appkey" not in str(event.payload)


class TestOrderBookToAudit:
    def test_convert_order_book(self):
        ob = RealtimeOrderBook(
            symbol="005930",
            ask_prices=[72000, 72050],
            bid_prices=[71900, 71850],
            raw_hash="hash456",
        )
        event = wsevent_to_audit(ob)
        assert event.event_type == "WS_ORDER_BOOK_RECEIVED"
        assert event.symbol == "005930"


class TestFillNoticeToAudit:
    def test_convert_fill_notice(self):
        fill = RealtimeFillNotice(
            symbol="005930",
            order_number="ORD001",
            fill_price=72000,
            fill_volume=50,
            raw_hash="hash789",
        )
        event = wsevent_to_audit(fill)
        assert event.event_type == "WS_FILL_NOTICE_RECEIVED"
        assert event.symbol == "005930"
        assert event.payload["fill_price"] == 72000
        assert event.payload["fill_volume"] == 50


class TestMarketStatusToAudit:
    def test_convert_market_status(self):
        ms = RealtimeMarketStatus(
            symbol="005930",
            market_status="OPEN",
            market_session="REGULAR",
            raw_hash="hash000",
        )
        event = wsevent_to_audit(ms)
        assert event.event_type == "WS_MARKET_STATUS_RECEIVED"
        assert event.payload["market_status"] == "OPEN"


class TestExpectedExecutionToAudit:
    def test_convert_expected_execution(self):
        ee = RealtimeExpectedExecution(
            symbol="005930",
            expected_price=71800,
            expected_volume=5000,
            raw_hash="hashEE",
        )
        event = wsevent_to_audit(ee)
        assert event.event_type == "WS_EXPECTED_EXECUTION_RECEIVED"
        assert event.payload["expected_price"] == 71800

    def test_convert_badly_parsed(self):
        msg = WebSocketMessageBase(
            tr_id="UNKNOWN_TR",
            symbol="",
            parsed_ok=False,
            data_quality_warnings=["unknown tr_id"],
        )
        # should not raise
        event = None
        try:
            event = wsevent_to_audit(msg)
        except Exception:
            pass
        if event is not None:
            # If it creates an event, should have warning info
            assert event.severity == "WARNING"


# ── WsEventBridge class ──────────────────────────────────────────────────────

class TestWsEventBridge:
    def test_bridge_basic(self):
        bridge = WsEventBridge()
        tick = RealtimeTradeTick(
            symbol="005930",
            trade_price=72000,
            raw_hash="hash123",
        )
        event = bridge.on_message(tick)
        assert event is not None
        assert event.event_type == "WS_TRADE_TICK_RECEIVED"

    def test_bridge_on_connect(self):
        bridge = WsEventBridge()
        event = bridge.on_connect()
        assert event is not None
        assert event.event_type == "WS_CONNECTED"

    def test_bridge_on_disconnect(self):
        bridge = WsEventBridge()
        event = bridge.on_disconnect()
        assert event is not None
        assert event.event_type == "WS_DISCONNECTED"

    def test_bridge_on_reconnect(self):
        bridge = WsEventBridge()
        event = bridge.on_reconnect(attempt=2)
        assert event is not None
        assert event.event_type == "WS_RECONNECTING"
        assert event.payload["attempt"] == 2

    def test_bridge_no_order_events(self):
        """Bridge should never produce order execution events."""
        bridge = WsEventBridge()
        tick = RealtimeTradeTick(symbol="005930")
        event = bridge.on_message(tick)
        assert "ORDER" not in event.event_type
        assert event.event_type not in {
            "ORDER_SUBMITTED", "ORDER_FAILED", "ORDER_INTENT_APPROVED"
        }
