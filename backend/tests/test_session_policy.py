"""Phase 2 — Session Policy 단위 테스트"""
import pytest
from session.session_state import TradingSessionState
from session.session_policy import (
    SessionPolicy,
    get_policy,
    can_new_buy,
)


class TestGetPolicy:
    """get_policy() 함수"""

    def test_closed_holiday_policy(self):
        p = get_policy(TradingSessionState.CLOSED_HOLIDAY)
        assert p.allow_new_buy is False
        assert p.allow_scan is False
        assert p.allow_sync is True
        assert p.allow_eod is False

    def test_regular_market_policy(self):
        p = get_policy(TradingSessionState.REGULAR_MARKET)
        assert p.allow_new_buy is True
        assert p.allow_scan is True
        assert p.allow_sell is True
        assert p.allow_cancel is True
        assert p.allow_sync is True
        assert p.allow_eod is False

    def test_late_market_policy(self):
        p = get_policy(TradingSessionState.LATE_MARKET)
        assert p.allow_new_buy is False
        assert p.allow_sell is True
        assert p.allow_scan is True
        assert p.allow_sync is True

    def test_closed_after_market_policy(self):
        p = get_policy(TradingSessionState.CLOSED_AFTER_MARKET)
        assert p.allow_new_buy is False
        assert p.allow_sell is False
        assert p.allow_sync is True
        assert p.allow_eod is True  # EOD only here

    def test_session_state_unknown_policy(self):
        p = get_policy(TradingSessionState.SESSION_STATE_UNKNOWN)
        assert p.allow_new_buy is False
        assert p.allow_scan is False
        assert p.allow_sell is False
        assert p.allow_cancel is False
        assert p.allow_sync is False
        assert p.allow_eod is False

    def test_pre_market_auction_policy(self):
        p = get_policy(TradingSessionState.PRE_MARKET_AUCTION)
        assert p.allow_new_buy is False
        assert p.allow_scan is True

    def test_closing_auction_policy(self):
        p = get_policy(TradingSessionState.CLOSING_AUCTION)
        assert p.allow_new_buy is False
        assert p.allow_sell is True

    def test_after_market_policy(self):
        p = get_policy(TradingSessionState.AFTER_MARKET)
        assert p.allow_new_buy is False
        assert p.allow_scan is False
        assert p.allow_sync is True

    def test_policy_frozen(self):
        p = get_policy(TradingSessionState.REGULAR_MARKET)
        with pytest.raises(AttributeError):
            p.allow_new_buy = False  # type: ignore

    def test_all_states_have_policy(self):
        """모든 TradingSessionState에 정책이 정의되어 있어야 함"""
        for state in TradingSessionState:
            p = get_policy(state)
            assert p.session_state == state


class TestCanNewBuy:
    """can_new_buy() 편의 함수"""

    def test_regular_market_allowed(self):
        assert can_new_buy(TradingSessionState.REGULAR_MARKET) is True

    def test_closed_holiday_blocked(self):
        assert can_new_buy(TradingSessionState.CLOSED_HOLIDAY) is False

    def test_late_market_blocked(self):
        assert can_new_buy(TradingSessionState.LATE_MARKET) is False

    def test_session_unknown_blocked(self):
        assert can_new_buy(TradingSessionState.SESSION_STATE_UNKNOWN) is False

    def test_closed_before_market_blocked(self):
        assert can_new_buy(TradingSessionState.CLOSED_BEFORE_MARKET) is False

    def test_pre_market_auction_blocked(self):
        assert can_new_buy(TradingSessionState.PRE_MARKET_AUCTION) is False

    def test_closing_auction_blocked(self):
        assert can_new_buy(TradingSessionState.CLOSING_AUCTION) is False

    def test_after_market_blocked(self):
        assert can_new_buy(TradingSessionState.AFTER_MARKET) is False

    def test_closed_after_market_blocked(self):
        assert can_new_buy(TradingSessionState.CLOSED_AFTER_MARKET) is False

    def test_only_regular_market_allowed(self):
        """REGULAR_MARKET만 허용"""
        allowed_count = sum(1 for s in TradingSessionState if can_new_buy(s))
        assert allowed_count == 1