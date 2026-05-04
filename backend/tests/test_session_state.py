"""Phase 2 — Session State 단위 테스트"""
import pytest
from session.session_state import (
    TradingSessionState,
    BUY_BLOCKED_STATES,
    BUY_ALLOWED_STATES,
)


class TestTradingSessionState:
    """TradingSessionState enum 기본"""

    def test_all_states_defined(self):
        assert len(TradingSessionState) == 9
        assert TradingSessionState.CLOSED_HOLIDAY
        assert TradingSessionState.CLOSED_BEFORE_MARKET
        assert TradingSessionState.PRE_MARKET_AUCTION
        assert TradingSessionState.REGULAR_MARKET
        assert TradingSessionState.LATE_MARKET
        assert TradingSessionState.CLOSING_AUCTION
        assert TradingSessionState.AFTER_MARKET
        assert TradingSessionState.CLOSED_AFTER_MARKET
        assert TradingSessionState.SESSION_STATE_UNKNOWN

    def test_session_state_unknown_present(self):
        assert TradingSessionState.SESSION_STATE_UNKNOWN.value == "SESSION_STATE_UNKNOWN"

    def test_regular_market_present(self):
        assert TradingSessionState.REGULAR_MARKET.value == "REGULAR_MARKET"

    def test_closed_holiday_present(self):
        assert TradingSessionState.CLOSED_HOLIDAY.value == "CLOSED_HOLIDAY"


class TestBuyBlockedStates:
    """매수 차단 상태 집합"""

    def test_closed_holiday_is_blocked(self):
        assert TradingSessionState.CLOSED_HOLIDAY in BUY_BLOCKED_STATES

    def test_closed_before_market_is_blocked(self):
        assert TradingSessionState.CLOSED_BEFORE_MARKET in BUY_BLOCKED_STATES

    def test_pre_market_auction_is_blocked(self):
        assert TradingSessionState.PRE_MARKET_AUCTION in BUY_BLOCKED_STATES

    def test_late_market_is_blocked(self):
        assert TradingSessionState.LATE_MARKET in BUY_BLOCKED_STATES

    def test_closing_auction_is_blocked(self):
        assert TradingSessionState.CLOSING_AUCTION in BUY_BLOCKED_STATES

    def test_after_market_is_blocked(self):
        assert TradingSessionState.AFTER_MARKET in BUY_BLOCKED_STATES

    def test_closed_after_market_is_blocked(self):
        assert TradingSessionState.CLOSED_AFTER_MARKET in BUY_BLOCKED_STATES

    def test_session_unknown_is_blocked(self):
        assert TradingSessionState.SESSION_STATE_UNKNOWN in BUY_BLOCKED_STATES

    def test_regular_market_not_blocked(self):
        """REGULAR_MARKET만 매수 차단 목록에 없음"""
        assert TradingSessionState.REGULAR_MARKET not in BUY_BLOCKED_STATES

    def test_blocked_count(self):
        """매수 차단 상태는 8개 (REGULAR_MARKET 제외)"""
        assert len(BUY_BLOCKED_STATES) == 8


class TestBuyAllowedStates:
    """매수 허용 상태 집합"""

    def test_regular_market_is_allowed(self):
        assert TradingSessionState.REGULAR_MARKET in BUY_ALLOWED_STATES

    def test_closed_holiday_not_allowed(self):
        assert TradingSessionState.CLOSED_HOLIDAY not in BUY_ALLOWED_STATES

    def test_late_market_not_allowed(self):
        assert TradingSessionState.LATE_MARKET not in BUY_ALLOWED_STATES

    def test_session_unknown_not_allowed(self):
        assert TradingSessionState.SESSION_STATE_UNKNOWN not in BUY_ALLOWED_STATES