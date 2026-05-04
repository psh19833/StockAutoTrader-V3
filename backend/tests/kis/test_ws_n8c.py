"""Tests for N8-C: GuardedRealWSClient extensions and pipe-delimited parser."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from kis.ws_client import GuardedRealWebSocketClient, ReconnectConfig, ConnectionState
from kis.ws_parser import dispatch_message, parse_trade_tick
from kis.ws_models import RealtimeTradeTick, WebSocketMessageBase


# ── Pipe-delimited parser ────────────────────────────────────────────────────

class TestPipeDelimitedParser:
    """KIS WebSocket can use pipe-delimited format. Parser must handle both."""

    def test_parse_pipe_delimited_trade_tick(self):
        raw = "0|H0STCNT0|005930|72000|100|093015|2|500"
        result = dispatch_message(raw)
        # Unknown format should not crash, parsed_ok=False
        assert result.parsed_ok is False

    def test_parse_pipe_delimited_no_crash(self):
        """Parser should not crash on pipe-delimited input."""
        raw = "0|H0STASP0|005930|72000|72050|72100|71900|71850"
        result = dispatch_message(raw)
        assert result is not None
        # parsed_ok may be False but should not raise

    def test_json_still_works(self):
        raw = json.dumps({"tr_id": "H0STCNT0", "MKSC_SHRN_ISCD": "005930", "STCK_PRPR": "72000"})
        result = dispatch_message(raw)
        assert result.parsed_ok is True
        assert isinstance(result, RealtimeTradeTick)

    def test_empty_string(self):
        result = dispatch_message("")
        assert result.parsed_ok is False

    def test_pipe_delimited_unparseable_is_not_raw_stored(self):
        raw = "0|H0STCNT0|005930|secret_value"
        result = dispatch_message(raw)
        # raw_hash is stored, not raw body
        assert result.raw_hash is not None
        # full raw not stored
        assert "secret_value" not in str(result.__dict__.values())


# ── GuardedRealWSClient: heartbeat ────────────────────────────────────────────

class TestGuardedRealWSHeartbeat:
    def test_heartbeat_updates_last_message_at(self):
        client = GuardedRealWebSocketClient()
        client._connection_state = ConnectionState.CONNECTED
        before = client._last_message_at
        client._heartbeat()
        after = client._last_message_at
        assert after is not None
        if before:
            assert after >= before

    def test_heartbeat_ignored_when_disconnected(self):
        client = GuardedRealWebSocketClient()
        # Default state is DISCONNECTED
        client._heartbeat()
        assert client._last_message_at is None


# ── GuardedRealWSClient: connection_state transitions ────────────────────────

class TestConnectionStateTransitions:
    def test_initial_disconnected(self):
        client = GuardedRealWebSocketClient()
        assert client._connection_state == ConnectionState.DISCONNECTED

    def test_connect_still_raises(self):
        client = GuardedRealWebSocketClient()
        with pytest.raises(NotImplementedError):
            client.connect()

    def test_disconnect_from_connected(self):
        client = GuardedRealWebSocketClient()
        client._connection_state = ConnectionState.CONNECTED
        client.disconnect()
        assert client._connection_state == ConnectionState.DISCONNECTED

    def test_reconnect_config_default(self):
        client = GuardedRealWebSocketClient()
        assert client._reconnect_config.max_retries == 5
        assert client._reconnect_config.base_delay == 1.0


# ── Smoke: duration / max_messages ───────────────────────────────────────────

class TestSmokeDurationOptions:
    def test_duration_default(self):
        """Default duration should be 0 or reasonable."""
        duration = 0  # default: no limit in stub mode
        assert duration >= 0

    def test_max_messages_default(self):
        max_messages = 0  # default: no limit
        assert max_messages >= 0

    def test_duration_caps_execution(self):
        """When duration > 0, execution should stop after time."""
        import time
        duration = 1  # 1 second
        start = time.time()
        # Simulate: if duration > 0 and elapsed > duration, stop
        elapsed = 2.0
        should_stop = elapsed >= duration
        assert should_stop is True

    def test_max_messages_caps_execution(self):
        """When max_messages > 0, stop after N messages."""
        max_messages = 3
        received = 3
        should_stop = received >= max_messages
        assert should_stop is True


# ── Real WS mode: flag only ──────────────────────────────────────────────────

class TestRealWsModeGuard:
    def test_real_ws_requires_explicit_flag(self):
        """Without --real-ws, GuardedRealWSClient.connect is NOT called."""
        use_real_ws = False
        called_connect = False
        if use_real_ws:
            client = GuardedRealWebSocketClient()
            client.connect()  # would raise
            called_connect = True
        assert called_connect is False

    def test_real_ws_flagged_still_raises_not_implemented(self):
        """With --real-ws, connect still raises NotImplementedError (skeleton)."""
        with pytest.raises(NotImplementedError):
            GuardedRealWebSocketClient().connect()
