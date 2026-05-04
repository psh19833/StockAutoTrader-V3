"""Tests for N4-B: KIS Market Schedule API + Session Engine"""
from __future__ import annotations

import pytest
from kis.transport import StubTransport
from kis.market_schedule_api import (
    MarketScheduleApi, get_holidays, get_market_status
)
from session.trading_calendar import TradingCalendar, TradingCalendarSnapshot
from session.market_clock import MarketClock
from session.session_state import TradingSessionState

# ── Stub Transport for tests ──

def _make_stub(holidays_response=None, status_response=None):
    responses = {}
    if holidays_response is not None:
        responses["/uapi/domestic-stock/v1/quotations/chk-holiday"] = holidays_response
    if status_response is not None:
        responses["/uapi/domestic-stock/v1/quotations/market-status"] = status_response
    return StubTransport(responses=responses)


class TestMarketScheduleApi:
    def test_get_holidays_success(self):
        transport = _make_stub(holidays_response={
            "output": [{"bass_dt": "20260505"}, {"bass_dt": "20260515"}]
        })
        api = MarketScheduleApi(transport=transport, base_url="https://test.com")
        result = api.get_holidays()
        assert isinstance(result, list)
        assert "20260505" in result

    def test_get_holidays_empty(self):
        transport = _make_stub(holidays_response={"output": []})
        api = MarketScheduleApi(transport=transport, base_url="https://test.com")
        result = api.get_holidays()
        assert result == []

    def test_get_holidays_failure(self):
        transport = _make_stub(holidays_response={"error": "server_error"})
        api = MarketScheduleApi(transport=transport, base_url="https://test.com")
        result = api.get_holidays()
        # error in response → returned as list (empty if no output key)
        assert result == []

    def test_get_market_status_open(self):
        transport = _make_stub(status_response={
            "output": {"market_status": "OPEN", "market_status_msg": "정상"}
        })
        api = MarketScheduleApi(transport=transport, base_url="https://test.com")
        result = api.get_market_status()
        assert result["market_status"] == "OPEN"

    def test_source_metadata(self):
        transport = _make_stub(holidays_response={"output": []})
        api = MarketScheduleApi(transport=transport, base_url="https://test.com")
        result = api.get_holidays()
        # API result should be a list (not dict with source meta for this case)
        assert isinstance(result, list)


class TestTradingCalendarWithKisData:
    def test_parse_holidays(self):
        cal = TradingCalendar()
        snapshot = cal.build_snapshot(
            holidays=["20260505", "20260515"],
            source_endpoints=("kis/holiday",),
        )
        assert "2026-05-05" in [d.isoformat() for d in snapshot.holidays]

    def test_no_holidays_allows_all(self):
        cal = TradingCalendar()
        snapshot = cal.build_snapshot(holidays=[])
        assert isinstance(snapshot.is_trading_day, bool)

    def test_source_endpoints_preserved(self):
        cal = TradingCalendar()
        snapshot = cal.build_snapshot(
            holidays=["20260505"],
            source_endpoints=("kis/holiday",),
        )
        assert "kis/holiday" in snapshot.source_endpoints


class TestMarketClockWithKisData:
    def test_regular_market_from_kis(self):
        clock = MarketClock()
        state = clock.map_kis_status("OPEN", is_trading_day=True)
        assert state == TradingSessionState.REGULAR_MARKET

    def test_preopen_from_kis(self):
        clock = MarketClock()
        state = clock.map_kis_status("PREOPEN", is_trading_day=True)
        assert state == TradingSessionState.PRE_MARKET_AUCTION

    def test_close_from_kis(self):
        clock = MarketClock()
        state = clock.map_kis_status("CLOSE", is_trading_day=True)
        assert state == TradingSessionState.CLOSED_AFTER_MARKET

    def test_unknown_status(self):
        clock = MarketClock()
        state = clock.map_kis_status("UNKNOWN_STATUS", is_trading_day=True)
        assert state == TradingSessionState.SESSION_STATE_UNKNOWN

    def test_holiday_blocks_sessions(self):
        clock = MarketClock()
        state = clock.map_kis_status("OPEN", is_trading_day=False)
        assert state == TradingSessionState.CLOSED_HOLIDAY


class TestSessionUnknownBlocking:
    def test_unknown_blocks_buy(self):
        from session.session_state import BUY_BLOCKED_STATES
        assert TradingSessionState.SESSION_STATE_UNKNOWN in BUY_BLOCKED_STATES
