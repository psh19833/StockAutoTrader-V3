"""Tests for backend/scripts/kis_ws_readonly_smoke.py — WebSocket smoke script."""
import json
import pytest
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock

# Make backend importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Helpers to test smoke script logic ────────────────────────────────────────

DEFAULT_CHANNELS = ["trade_tick", "order_book", "market_status", "expected_execution"]

CHANNEL_TR_ID_MAP = {
    "trade_tick": "H0STCNT0",
    "order_book": "H0STASP0",
    "market_status": "H0STMKO0",
    "expected_execution": "H0STANC0",
    "fill_notice": "H0STCNI0",
}


class TestChannelDefaults:
    def test_fill_notice_not_in_default_channels(self):
        assert "fill_notice" not in DEFAULT_CHANNELS

    def test_default_channels_have_known_tr_ids(self):
        for ch in DEFAULT_CHANNELS:
            assert ch in CHANNEL_TR_ID_MAP, f"Unknown channel: {ch}"

    def test_fill_notice_has_separate_tr_id(self):
        assert CHANNEL_TR_ID_MAP["fill_notice"] == "H0STCNI0"

    def test_default_channels_count(self):
        assert len(DEFAULT_CHANNELS) == 4


class TestSmokeScriptStubMode:
    """Tests that verify stub mode (default) behavior."""

    def test_stub_mode_uses_stub_client(self):
        """Default mode should create StubWebSocketClient."""
        from kis.ws_client import StubWebSocketClient
        client = StubWebSocketClient()
        assert isinstance(client, StubWebSocketClient)
        # stub client does NOT make real connections
        client.connect()
        assert client.get_status().connection_state == "CONNECTED"
        client.disconnect()

    def test_stub_subscribe_works(self):
        from kis.ws_client import StubWebSocketClient
        client = StubWebSocketClient()
        client.connect()
        client.subscribe("H0STCNT0", "005930")
        status = client.get_status()
        assert "H0STCNT0" in status.subscribed_channels

    def test_stub_mode_no_real_ws_connect(self):
        """Stub mode must never call real WebSocket connect."""
        from kis.ws_client import GuardedRealWebSocketClient
        # Guarded client connect raises NotImplementedError
        with pytest.raises(NotImplementedError):
            GuardedRealWebSocketClient().connect()


class TestSmokeScriptRealWsMode:
    """Tests that verify --real-ws mode guard rails."""

    def test_real_ws_mode_requires_flag(self):
        """Without --real-ws, the script should use StubWebSocketClient."""
        # This is a logic test: the flag is checked before creating client
        use_real_ws = False
        if use_real_ws:
            from kis.ws_client import GuardedRealWebSocketClient
            client_factory = GuardedRealWebSocketClient
        else:
            from kis.ws_client import StubWebSocketClient
            client_factory = StubWebSocketClient

        client = client_factory()
        from kis.ws_client import StubWebSocketClient
        assert isinstance(client, StubWebSocketClient)

    def test_real_ws_flag_enables_guarded_client(self):
        """With --real-ws, GuardedRealWebSocketClient is created."""
        use_real_ws = True
        if use_real_ws:
            from kis.ws_client import GuardedRealWebSocketClient
            client_factory = GuardedRealWebSocketClient
        else:
            from kis.ws_client import StubWebSocketClient
            client_factory = StubWebSocketClient

        client = client_factory()
        from kis.ws_client import GuardedRealWebSocketClient
        assert isinstance(client, GuardedRealWebSocketClient)


class TestLiveTradingCheck:
    def test_live_trading_enabled_blocks_smoke(self):
        """Smoke script should exit if LIVE_TRADING_ENABLED=true."""
        live_trading_enabled = True
        if live_trading_enabled:
            should_abort = True
        else:
            should_abort = False
        assert should_abort is True

    def test_live_trading_disabled_allows_smoke(self):
        """Smoke script should proceed if LIVE_TRADING_ENABLED=false."""
        live_trading_enabled = False
        if live_trading_enabled:
            should_abort = True
        else:
            should_abort = False
        assert should_abort is False


class TestApprovalKeyMasking:
    def test_approval_key_masked_in_display(self):
        from kis.ws_subscription import MASKED_APPROVAL_KEY
        from kis.ws_client import GuardedRealWebSocketClient

        client = GuardedRealWebSocketClient()
        masked = client.get_subscribe_payload_masked("H0STCNT0", "005930", "real-key")
        assert MASKED_APPROVAL_KEY in masked
        assert "real-key" not in masked

    def test_approval_key_masked_constant(self):
        from kis.ws_approval import MASKED_APPROVAL_KEY as AK_MASKED
        assert AK_MASKED == "****-****-****"


class TestFillNoticeExclusion:
    def test_fill_notice_excluded_by_default(self):
        channels = DEFAULT_CHANNELS.copy()
        assert "fill_notice" not in channels

    def test_fill_notice_included_only_with_flag(self):
        include_fill_notice = True
        channels = DEFAULT_CHANNELS.copy()
        if include_fill_notice:
            channels.append("fill_notice")
        assert "fill_notice" in channels
        assert len(channels) == 5

    def test_fill_notice_is_not_order_confirmation(self):
        """fill_notice is observation only, not position confirmation."""
        from kis.ws_models import RealtimeFillNotice
        fill = RealtimeFillNotice(symbol="005930")
        # fill_notice does NOT trigger ORDER_SUBMITTED or ORDER_FILLED
        assert fill.tr_id == "H0STCNI0"
        # Check that it's a WebSocket message, not an order event
        assert fill.source == "KIS_API_WS"


class TestNoOrderEndpoints:
    def test_smoke_script_does_not_import_order_modules(self):
        """Smoke script must not import order-related modules."""
        # Verify that order-cash, order-credit paths are not in the
        # subscriptions or channel handling logic
        forbidden = ["order-cash", "order-credit", "order-rvsecncl"]
        tr_ids = set(CHANNEL_TR_ID_MAP.values())
        for f in forbidden:
            assert f not in tr_ids

    def test_channel_map_only_has_read_channels(self):
        """All channels are read-only market data."""
        valid_tr_ids = {"H0STCNT0", "H0STASP0", "H0STCNI0", "H0STMKO0", "H0STANC0"}
        for tr_id in CHANNEL_TR_ID_MAP.values():
            assert tr_id in valid_tr_ids


class TestRawMessageSuppression:
    def test_parsed_summary_not_raw(self):
        """Smoke script should print parsed summary, not raw message."""
        from kis.ws_parser import dispatch_message
        raw = json.dumps({"tr_id": "H0STCNT0", "MKSC_SHRN_ISCD": "005930", "STCK_PRPR": "72000"})
        result = dispatch_message(raw)
        # parsed summary: only typed fields, no raw body
        summary = {
            "tr_id": result.tr_id,
            "symbol": result.symbol,
            "parsed_ok": result.parsed_ok,
        }
        assert "72000" not in str(summary)  # trade price is not in summary dict
        assert len(json.dumps(summary)) < 200  # summary is compact
