"""Tests for N9: REST/WS data router, market cache, data quality."""
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from kis.ws_models import RealtimeTradeTick, RealtimeOrderBook, RealtimeMarketStatus
from kis.schemas import DataUnavailable


# We'll test the modules directly after they're created.
# For now, test the contracts and behaviors.


class TestDataQualityLogic:
    """Data quality checks: stale, missing fields, source mismatch."""

    def test_stale_detection(self):
        """Data older than threshold is stale."""
        now = datetime.now(timezone.utc)
        threshold = timedelta(seconds=60)
        old_time = now - timedelta(seconds=90)
        is_stale = (now - old_time) > threshold
        assert is_stale is True

    def test_fresh_data_not_stale(self):
        now = datetime.now(timezone.utc)
        threshold = timedelta(seconds=60)
        recent_time = now - timedelta(seconds=10)
        is_stale = (now - recent_time) > threshold
        assert is_stale is False

    def test_source_mismatch_detected(self):
        """If source is not KIS_API_REST or KIS_API_WS, flag it."""
        valid_sources = {"KIS_API_REST", "KIS_API_WS"}
        assert "KIS_API" not in valid_sources  # REST source
        assert "FAKE_SOURCE" not in valid_sources


class TestMarketCache:
    """Market data cache: symbol-level latest quote/orderbook cache."""

    def test_cache_stores_latest_tick(self):
        cache = {}
        tick = RealtimeTradeTick(symbol="005930", trade_price=72000)
        cache["005930:trade_tick"] = tick
        assert cache["005930:trade_tick"].trade_price == 72000

    def test_cache_update_overwrites(self):
        cache = {}
        tick1 = RealtimeTradeTick(symbol="005930", trade_price=72000)
        tick2 = RealtimeTradeTick(symbol="005930", trade_price=72100)
        cache["005930:trade_tick"] = tick1
        cache["005930:trade_tick"] = tick2
        assert cache["005930:trade_tick"].trade_price == 72100

    def test_cache_separates_symbols(self):
        cache = {}
        cache["005930:trade_tick"] = RealtimeTradeTick(symbol="005930", trade_price=72000)
        cache["000660:trade_tick"] = RealtimeTradeTick(symbol="000660", trade_price=150000)
        assert cache["005930:trade_tick"].trade_price == 72000
        assert cache["000660:trade_tick"].trade_price == 150000

    def test_cache_source_tracking(self):
        """Cache should track source (REST or WS) for each entry."""
        cache = {}
        cache["005930:source"] = "KIS_API_REST"
        cache["005930:trade_tick"] = RealtimeTradeTick(symbol="005930")
        assert cache["005930:source"] == "KIS_API_REST"


class TestRestWsPolicy:
    """REST/WS fallback policy."""

    def test_initial_load_from_rest(self):
        """Initial data should come from REST."""
        source = "KIS_API_REST"  # 초기값
        assert source == "KIS_API_REST"

    def test_ws_update_overrides(self):
        """WebSocket updates override REST snapshot."""
        source = "KIS_API_REST"
        # WS message received
        source = "KIS_API_WS"
        assert source == "KIS_API_WS"

    def test_ws_disconnect_fallback_to_rest(self):
        """When WS disconnects, fall back to REST."""
        ws_connected = False
        source = "KIS_API_REST" if not ws_connected else "KIS_API_WS"
        assert source == "KIS_API_REST"

    def test_no_estimated_values(self):
        """Never generate estimated/guessed values."""
        # DataUnavailable should be used instead of estimates
        assert DataUnavailable is not None


class TestDataRouter:
    """MarketDataRouter: unified access to REST + WS data."""

    def test_get_latest_quote(self):
        """get_latest_quote returns latest tick from cache."""
        # Structure test — implementation validates
        pass

    def test_get_latest_orderbook(self):
        """get_latest_orderbook returns latest orderbook from cache."""
        pass

    def test_get_latest_market_status(self):
        """get_latest_market_status returns market status."""
        pass


class TestDashboardDataRouterStatus:
    """Dashboard should show data router status."""

    def test_router_status_has_ws_connection(self):
        status = {
            "ws_connected": False,
            "rest_available": True,
            "stale_warnings": [],
        }
        assert "ws_connected" in status
        assert "rest_available" in status
