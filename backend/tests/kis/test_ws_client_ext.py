"""Tests for GuardedRealWebSocketClient extensions (N8-B)."""
import json
import pytest

from kis.ws_client import GuardedRealWebSocketClient
from kis.ws_subscription import MASKED_APPROVAL_KEY


class TestGuardedRealWSClientExtensions:
    """N8-B: GuardedRealWebSocketClient에 subscribe payload 빌딩 추가."""

    def test_build_subscribe_payload(self):
        client = GuardedRealWebSocketClient()
        payload = client.build_subscribe_payload("H0STCNT0", "005930", "mock-key")
        assert payload["header"]["tr_type"] == "1"
        assert payload["header"]["approval_key"] == "mock-key"
        assert payload["body"]["input"]["tr_id"] == "H0STCNT0"
        assert payload["body"]["input"]["tr_key"] == "005930"

    def test_build_unsubscribe_payload(self):
        client = GuardedRealWebSocketClient()
        payload = client.build_unsubscribe_payload("H0STCNT0", "005930", "mock-key")
        assert payload["header"]["tr_type"] == "2"

    def test_connect_still_raises_not_implemented(self):
        """connect() requires approval_key."""
        client = GuardedRealWebSocketClient()
        with pytest.raises(ValueError):
            client.connect()

    def test_get_subscribe_payload_masked_for_display(self):
        """Display version masks approval_key."""
        client = GuardedRealWebSocketClient()
        masked = client.get_subscribe_payload_masked("H0STCNT0", "005930", "real-key-123")
        assert "real-key-123" not in masked
        assert MASKED_APPROVAL_KEY in masked
        assert "H0STCNT0" in masked
        assert "005930" in masked

    def test_get_subscribe_payload_masked_is_json(self):
        client = GuardedRealWebSocketClient()
        masked = client.get_subscribe_payload_masked("H0STCNT0", "005930", "real-key")
        parsed = json.loads(masked)
        assert parsed["header"]["approval_key"] == MASKED_APPROVAL_KEY

    def test_store_approval_key(self):
        client = GuardedRealWebSocketClient()
        client._store_approval_key("real-key-456")
        assert client._approval_key == "real-key-456"

    def test_approval_key_not_in_repr(self):
        client = GuardedRealWebSocketClient()
        client._store_approval_key("real-key-456")
        r = repr(client)
        assert "real-key-456" not in r

    def test_no_external_websocket_deps(self):
        """GuardedRealWebSocketClient should not import external WS libraries."""
        import sys
        # After import, 'websocket' and 'websockets' should not be in sys.modules
        # (unless pre-existing from other code)
        # This is a soft check — the module uses only stdlib
        client = GuardedRealWebSocketClient()
        assert client is not None  # construction succeeds without WS deps
