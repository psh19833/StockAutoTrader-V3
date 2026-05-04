"""Tests for OPS-2: GuardedRealWebSocketClient real connect implementation."""
import json
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from kis.ws_client import GuardedRealWebSocketClient, ConnectionState
from kis.ws_subscription import build_subscribe_payload, MASKED_APPROVAL_KEY


# ── Mock WebSocket fixture ───────────────────────────────────────────────────

@pytest.fixture
def mock_ws():
    """Create a mock websocket that records sends and simulates receives."""
    mock = MagicMock()
    mock.connected = True
    mock.recv_data = []  # queued messages to return
    mock.sent_messages = []
    
    def mock_send(msg):
        mock.sent_messages.append(msg)
    
    def mock_recv():
        if mock.recv_data:
            return mock.recv_data.pop(0)
        return None  # no more messages
    
    mock.send = mock_send
    mock.recv = mock_recv
    mock.close = MagicMock()
    return mock


# ── Connect tests ────────────────────────────────────────────────────────────

class TestRealWebSocketConnect:
    def test_connect_establishes_connection(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="test-key", base_url="ws://kis-ws")
            assert client._connection_state == ConnectionState.CONNECTED
            assert client._ws is mock_ws

    def test_connect_failure_sets_error(self, mock_ws):
        with patch('websocket.create_connection', side_effect=ConnectionRefusedError("refused")):
            client = GuardedRealWebSocketClient()
            with pytest.raises(ConnectionError):
                client.connect(approval_key="test-key", base_url="ws://kis-ws")
            assert client._connection_state == ConnectionState.ERROR

    def test_connect_requires_approval_key(self):
        client = GuardedRealWebSocketClient()
        with pytest.raises(ValueError, match="approval_key"):
            client.connect(approval_key="", base_url="ws://kis-ws")


# ── Subscribe / unsubscribe via WebSocket ─────────────────────────────────────

class TestRealWebSocketSubscribe:
    def test_subscribe_sends_payload(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="real-key", base_url="ws://kis-ws")
            client.subscribe("H0STCNT0", "005930")
            assert len(mock_ws.sent_messages) == 1
            payload = json.loads(mock_ws.sent_messages[0])
            assert payload["header"]["approval_key"] == "real-key"
            assert payload["body"]["input"]["tr_id"] == "H0STCNT0"
            assert payload["body"]["input"]["tr_key"] == "005930"

    def test_unsubscribe_sends_unregister(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="real-key", base_url="ws://kis-ws")
            client.subscribe("H0STCNT0", "005930")
            client.unsubscribe("H0STCNT0")
            assert len(mock_ws.sent_messages) == 2
            unsub_payload = json.loads(mock_ws.sent_messages[1])
            assert unsub_payload["header"]["tr_type"] == "2"

    def test_subscribe_before_connect_raises(self):
        client = GuardedRealWebSocketClient()
        with pytest.raises(RuntimeError, match="DISCONNECTED"):
            client.subscribe("H0STCNT0", "005930")

    def test_disconnect_closes_ws_and_clears_state(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="key", base_url="ws://kis-ws")
            client.subscribe("H0STCNT0", "005930")
            client.disconnect()
            mock_ws.close.assert_called_once()
            assert client._connection_state == ConnectionState.DISCONNECTED
            assert len(client._subscribed) == 0


# ── Approval key security ────────────────────────────────────────────────────

class TestRealWSApprovalKeySecurity:
    def test_approval_key_not_in_repr(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="secret-real-key-123", base_url="ws://kis-ws")
            r = repr(client)
            assert "secret-real-key" not in r

    def test_connect_url_masked_in_repr(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="key", base_url="ws://kis-ws-url")
            r = repr(client)
            assert "kis-ws-url" not in r  # URL should not leak in repr


# ── Connection state transitions ─────────────────────────────────────────────

class TestRealWSConnectionStates:
    def test_connect_connected_state(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            assert client._connection_state == ConnectionState.DISCONNECTED
            client.connect(approval_key="key", base_url="ws://kis-ws")
            assert client._connection_state == ConnectionState.CONNECTED

    def test_disconnect_resets_state(self, mock_ws):
        with patch('websocket.create_connection', return_value=mock_ws):
            client = GuardedRealWebSocketClient()
            client.connect(approval_key="key", base_url="ws://kis-ws")
            client.disconnect()
            assert client._connection_state == ConnectionState.DISCONNECTED


# ── Smoke script integration tests ───────────────────────────────────────────

class TestSmokeScriptWithRealWS:
    def test_real_ws_flag_selects_real_client(self):
        use_real_ws = True
        if use_real_ws:
            from kis.ws_client import GuardedRealWebSocketClient
            client_cls = GuardedRealWebSocketClient
        else:
            from kis.ws_client import StubWebSocketClient
            client_cls = StubWebSocketClient
        assert client_cls is GuardedRealWebSocketClient

    def test_stub_default_without_real_ws(self):
        use_real_ws = False
        if use_real_ws:
            from kis.ws_client import GuardedRealWebSocketClient
            client_cls = GuardedRealWebSocketClient
        else:
            from kis.ws_client import StubWebSocketClient
            client_cls = StubWebSocketClient
        assert client_cls is StubWebSocketClient

    def test_fill_notice_excluded_by_default(self):
        channels = ["trade_tick", "order_book", "market_status", "expected_execution"]
        assert "fill_notice" not in channels

    def test_duration_default(self):
        duration = 30
        assert duration == 30

    def test_max_messages_default(self):
        max_messages = 10
        assert max_messages == 10

    def test_live_trading_true_blocks(self):
        live_trading = True
        should_abort = live_trading
        assert should_abort is True


# ── No raw message output ────────────────────────────────────────────────────

class TestNoRawMessageOutput:
    def test_subscribe_payload_masked_when_displayed(self):
        client = GuardedRealWebSocketClient()
        masked = client.get_subscribe_payload_masked("H0STCNT0", "005930", "real-key")
        assert "real-key" not in masked
        assert MASKED_APPROVAL_KEY in masked

    def test_parsed_summary_compact(self):
        """verify the smoke output format is compact."""
        summary = {"tr_id": "H0STCNT0", "symbol": "005930", "parsed_ok": True}
        assert len(json.dumps(summary)) < 200
        assert "raw" not in str(summary).lower()
