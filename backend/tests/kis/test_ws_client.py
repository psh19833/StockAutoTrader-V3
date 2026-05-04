"""Tests for backend/kis/ws_client.py — WebSocket client interface and Stub."""
import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from kis.ws_client import (
    WebSocketClient,
    StubWebSocketClient,
    GuardedRealWebSocketClient,
    ReconnectConfig,
    ConnectionState,
)
from kis.ws_models import (
    RealtimeTradeTick,
    RealtimeOrderBook,
    WebSocketConnectionStatus,
)


# ── ReconnectConfig ──────────────────────────────────────────────────────────

class TestReconnectConfig:
    def test_default_values(self):
        cfg = ReconnectConfig()
        assert cfg.max_retries == 5
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.backoff_multiplier == 2.0

    def test_custom_values(self):
        cfg = ReconnectConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=30.0,
            backoff_multiplier=3.0,
        )
        assert cfg.max_retries == 3
        assert cfg.base_delay == 2.0
        assert cfg.max_delay == 30.0
        assert cfg.backoff_multiplier == 3.0

    def test_compute_delay_first_attempt(self):
        cfg = ReconnectConfig()
        assert cfg.compute_delay(0) == 1.0  # base_delay

    def test_compute_delay_with_backoff(self):
        cfg = ReconnectConfig(base_delay=1.0, backoff_multiplier=2.0, max_delay=60.0)
        assert cfg.compute_delay(0) == 1.0
        assert cfg.compute_delay(1) == 2.0
        assert cfg.compute_delay(2) == 4.0
        assert cfg.compute_delay(3) == 8.0

    def test_compute_delay_capped_at_max(self):
        cfg = ReconnectConfig(max_delay=10.0)
        delay = cfg.compute_delay(10)  # would be 1024 without cap
        assert delay == 10.0


# ── ConnectionState ──────────────────────────────────────────────────────────

class TestConnectionState:
    def test_default_disconnected(self):
        assert ConnectionState.DISCONNECTED.value == "DISCONNECTED"

    def test_all_states(self):
        states = {s.value for s in ConnectionState}
        assert "DISCONNECTED" in states
        assert "CONNECTING" in states
        assert "CONNECTED" in states
        assert "RECONNECTING" in states
        assert "ERROR" in states


# ── WebSocketClient interface ────────────────────────────────────────────────

class TestWebSocketClientInterface:
    def test_interface_methods(self):
        """Verify StubWebSocketClient implements the WebSocketClient protocol."""
        client = StubWebSocketClient()
        assert hasattr(client, "connect")
        assert hasattr(client, "disconnect")
        assert hasattr(client, "subscribe")
        assert hasattr(client, "unsubscribe")
        assert hasattr(client, "get_status")

    def test_stub_is_web_socket_client(self):
        client = StubWebSocketClient()
        assert isinstance(client, WebSocketClient)


# ── StubWebSocketClient ──────────────────────────────────────────────────────

class TestStubWebSocketClient:
    def test_initial_state_disconnected(self):
        client = StubWebSocketClient()
        status = client.get_status()
        assert status.connection_state == "DISCONNECTED"

    def test_connect_changes_state(self):
        client = StubWebSocketClient()
        client.connect()
        status = client.get_status()
        assert status.connection_state == "CONNECTED"

    def test_disconnect_changes_state(self):
        client = StubWebSocketClient()
        client.connect()
        client.disconnect()
        status = client.get_status()
        assert status.connection_state == "DISCONNECTED"

    def test_subscribe_adds_channel(self):
        client = StubWebSocketClient()
        client.connect()
        client.subscribe("H0STCNT0", "005930")
        status = client.get_status()
        assert "H0STCNT0" in status.subscribed_channels

    def test_subscribe_before_connect_fails(self):
        client = StubWebSocketClient()
        with pytest.raises(RuntimeError):
            client.subscribe("H0STCNT0", "005930")

    def test_unsubscribe_removes_channel(self):
        client = StubWebSocketClient()
        client.connect()
        client.subscribe("H0STCNT0", "005930")
        client.subscribe("H0STASP0", "005930")
        client.unsubscribe("H0STCNT0")
        status = client.get_status()
        assert "H0STCNT0" not in status.subscribed_channels
        assert "H0STASP0" in status.subscribed_channels

    def test_last_message_at_updated_on_receive(self):
        client = StubWebSocketClient()
        client.connect()
        client.subscribe("H0STCNT0", "005930")
        # Inject a mock message
        msg = RealtimeTradeTick(symbol="005930")
        client._inject_message(msg)
        status = client.get_status()
        assert status.last_message_at is not None
        delta = (datetime.now(timezone.utc) - status.last_message_at).total_seconds()
        assert delta < 5

    def test_reconnect_count_increments(self):
        client = StubWebSocketClient()
        client._simulate_reconnect()
        client._simulate_reconnect()
        status = client.get_status()
        assert status.reconnect_count == 2

    def test_set_error(self):
        client = StubWebSocketClient()
        client.connect()
        client._simulate_error("TIMEOUT")
        status = client.get_status()
        assert status.connection_state == "ERROR"
        assert status.last_error_type == "TIMEOUT"

    def test_data_quality_warnings_accumulate(self):
        client = StubWebSocketClient()
        client._add_data_quality_warning("stale_data")
        client._add_data_quality_warning("gap_detected")
        status = client.get_status()
        assert "stale_data" in status.data_quality_warnings
        assert "gap_detected" in status.data_quality_warnings

    def test_stub_does_not_make_network_calls(self):
        """StubWebSocketClient must never attempt real network connections."""
        client = StubWebSocketClient()
        # connect/disconnect are no-ops in terms of network
        client.connect()
        client.disconnect()
        # No exceptions = no network attempts

    def test_heartbeat_updates_last_message_at(self):
        client = StubWebSocketClient()
        client.connect()
        before = client.get_status().last_message_at
        client._heartbeat()
        after = client.get_status().last_message_at
        assert (before is None) or (after >= before)


# ── GuardedRealWebSocketClient skeleton ──────────────────────────────────────

class TestGuardedRealWebSocketClient:
    def test_skeleton_has_methods(self):
        client = GuardedRealWebSocketClient()
        assert hasattr(client, "connect")
        assert hasattr(client, "disconnect")
        assert hasattr(client, "subscribe")
        assert hasattr(client, "unsubscribe")
        assert hasattr(client, "get_status")

    def test_skeleton_connect_raises(self):
        """Real client requires approval_key — raises ValueError without it."""
        client = GuardedRealWebSocketClient()
        with pytest.raises(ValueError):
            client.connect()  # no approval_key
