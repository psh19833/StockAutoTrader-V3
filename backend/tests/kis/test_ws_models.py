"""Tests for backend/kis/ws_models.py — KIS WebSocket data models."""
import json
import time
from datetime import datetime, timezone

from kis.ws_models import (
    WebSocketMessageBase,
    RealtimeTradeTick,
    RealtimeOrderBook,
    RealtimeFillNotice,
    RealtimeMarketStatus,
    RealtimeExpectedExecution,
    WebSocketConnectionStatus,
)


# ── WebSocketMessageBase ────────────────────────────────────────────────────

class TestWebSocketMessageBase:
    def test_required_fields(self):
        msg = WebSocketMessageBase(
            source="KIS_API_WS",
            tr_id="H0STCNT0",
            symbol="005930",
        )
        assert msg.source == "KIS_API_WS"
        assert msg.tr_id == "H0STCNT0"
        assert msg.symbol == "005930"
        assert isinstance(msg.received_at, datetime)
        assert msg.parsed_ok is True
        assert msg.data_quality_warnings == []

    def test_received_at_is_now_utc_by_default(self):
        msg = WebSocketMessageBase(
            source="KIS_API_WS",
            tr_id="H0STCNT0",
            symbol="005930",
        )
        now = datetime.now(timezone.utc)
        delta = abs((msg.received_at - now).total_seconds())
        assert delta < 5  # within 5 seconds of now

    def test_parsed_ok_false(self):
        msg = WebSocketMessageBase(
            source="KIS_API_WS",
            tr_id="UNKNOWN_TR",
            symbol="",
            parsed_ok=False,
            data_quality_warnings=["unknown tr_id"],
        )
        assert msg.parsed_ok is False
        assert "unknown tr_id" in msg.data_quality_warnings

    def test_raw_hash_is_none_by_default(self):
        msg = WebSocketMessageBase(
            source="KIS_API_WS",
            tr_id="H0STCNT0",
            symbol="005930",
        )
        assert msg.raw_hash is None

    def test_can_set_raw_hash(self):
        msg = WebSocketMessageBase(
            source="KIS_API_WS",
            tr_id="H0STCNT0",
            symbol="005930",
            raw_hash="abc123def",
        )
        assert msg.raw_hash == "abc123def"


# ── RealtimeTradeTick ───────────────────────────────────────────────────────

class TestRealtimeTradeTick:
    def test_fields(self):
        now = datetime.now(timezone.utc)
        tick = RealtimeTradeTick(
            source="KIS_API_WS",
            symbol="005930",
            trade_price=72000,
            trade_volume=100,
            trade_time="093015",
            change_sign="2",
            change_price=500,
            ask_price=72050,
            bid_price=71950,
            trade_type="1",
            received_at=now,
            raw_hash="hash123",
        )
        assert tick.trade_price == 72000
        assert tick.trade_volume == 100
        assert tick.trade_time == "093015"
        assert tick.change_sign == "2"
        assert tick.change_price == 500
        assert tick.ask_price == 72050
        assert tick.bid_price == 71950
        assert tick.trade_type == "1"
        assert tick.tr_id == "H0STCNT0"
        assert tick.parsed_ok is True

    def test_defaults(self):
        tick = RealtimeTradeTick(
            source="KIS_API_WS",
            symbol="005930",
        )
        assert tick.trade_price is None
        assert tick.trade_volume is None
        assert tick.trade_time is None


# ── RealtimeOrderBook ────────────────────────────────────────────────────────

class TestRealtimeOrderBook:
    def test_fields(self):
        now = datetime.now(timezone.utc)
        ob = RealtimeOrderBook(
            source="KIS_API_WS",
            symbol="005930",
            ask_prices=[72000, 72050, 72100],
            ask_volumes=[50, 30, 20],
            bid_prices=[71900, 71850, 71800],
            bid_volumes=[40, 60, 10],
            total_ask_volume=100,
            total_bid_volume=110,
            received_at=now,
            raw_hash="hash456",
        )
        assert ob.ask_prices == [72000, 72050, 72100]
        assert ob.bid_volumes == [40, 60, 10]
        assert ob.total_ask_volume == 100
        assert ob.total_bid_volume == 110
        assert ob.tr_id == "H0STASP0"

    def test_empty_arrays_default(self):
        ob = RealtimeOrderBook(
            source="KIS_API_WS",
            symbol="005930",
        )
        assert ob.ask_prices == []
        assert ob.bid_prices == []
        assert ob.total_ask_volume is None


# ── RealtimeFillNotice ──────────────────────────────────────────────────────

class TestRealtimeFillNotice:
    def test_fields(self):
        now = datetime.now(timezone.utc)
        fill = RealtimeFillNotice(
            source="KIS_API_WS",
            symbol="005930",
            order_number="ORD001",
            fill_price=72000,
            fill_volume=50,
            fill_time="093015",
            order_type="01",
            received_at=now,
            raw_hash="hash789",
        )
        assert fill.symbol == "005930"
        assert fill.order_number == "ORD001"
        assert fill.fill_price == 72000
        assert fill.fill_volume == 50
        assert fill.tr_id == "H0STCNI0"

    def test_fill_is_confirmation(self):
        fill = RealtimeFillNotice(
            source="KIS_API_WS",
            symbol="005930",
            order_number="ORD001",
        )
        # 체결 확정용으로 사용됨을 나타내는 속성
        assert fill.parsed_ok is True


# ── RealtimeMarketStatus ────────────────────────────────────────────────────

class TestRealtimeMarketStatus:
    def test_fields(self):
        now = datetime.now(timezone.utc)
        status = RealtimeMarketStatus(
            source="KIS_API_WS",
            symbol="005930",
            market_status="OPEN",
            market_session="REGULAR",
            received_at=now,
            raw_hash="hash000",
        )
        assert status.market_status == "OPEN"
        assert status.market_session == "REGULAR"
        assert status.tr_id == "H0STMKO0"


# ── RealtimeExpectedExecution ───────────────────────────────────────────────

class TestRealtimeExpectedExecution:
    def test_fields(self):
        now = datetime.now(timezone.utc)
        ee = RealtimeExpectedExecution(
            source="KIS_API_WS",
            symbol="005930",
            expected_price=71800,
            expected_volume=5000,
            expected_change="DOWN",
            received_at=now,
            raw_hash="hashEE",
        )
        assert ee.expected_price == 71800
        assert ee.expected_volume == 5000
        assert ee.expected_change == "DOWN"
        assert ee.tr_id == "H0STANC0"


# ── WebSocketConnectionStatus ───────────────────────────────────────────────

class TestWebSocketConnectionStatus:
    def test_default_connection_status(self):
        status = WebSocketConnectionStatus()
        assert status.connection_state == "DISCONNECTED"
        assert status.subscribed_channels == []
        assert status.last_message_at is None
        assert status.reconnect_count == 0
        assert status.last_error_type is None
        assert status.data_quality_warnings == []

    def test_connected_status(self):
        now = datetime.now(timezone.utc)
        status = WebSocketConnectionStatus(
            connection_state="CONNECTED",
            subscribed_channels=["H0STCNT0", "H0STASP0"],
            last_message_at=now,
            reconnect_count=2,
            last_error_type="TIMEOUT",
            data_quality_warnings=["stale data"],
        )
        assert status.connection_state == "CONNECTED"
        assert "H0STCNT0" in status.subscribed_channels
        assert status.reconnect_count == 2
        assert status.last_error_type == "TIMEOUT"
        assert "stale data" in status.data_quality_warnings

    def test_source_is_kis_api_ws(self):
        status = WebSocketConnectionStatus()
        assert status.source == "KIS_API_WS"


# ── serialization / masking ─────────────────────────────────────────────────

class TestSerialization:
    def test_trade_tick_serializable(self):
        tick = RealtimeTradeTick(
            source="KIS_API_WS",
            symbol="005930",
            trade_price=72000,
            trade_volume=100,
        )
        d = tick.__dict__
        assert d["trade_price"] == 72000

    def test_web_socket_connection_status_serializable(self):
        status = WebSocketConnectionStatus(connection_state="CONNECTED")
        d = status.__dict__
        assert d["connection_state"] == "CONNECTED"
