"""Phase 2 — Session Events 단위 테스트"""
import pytest
from datetime import datetime, timezone
from session.session_events import (
    SessionEventType,
    SessionEvent,
)


class TestSessionEventType:
    """SessionEventType enum"""

    def test_all_event_types_defined(self):
        assert len(SessionEventType) == 11

    def test_trading_day_checked(self):
        assert SessionEventType.TRADING_DAY_CHECKED.value == "TRADING_DAY_CHECKED"

    def test_market_session_evaluated(self):
        assert SessionEventType.MARKET_SESSION_EVALUATED.value == "MARKET_SESSION_EVALUATED"

    def test_session_state_changed(self):
        assert SessionEventType.SESSION_STATE_CHANGED.value == "SESSION_STATE_CHANGED"

    def test_pre_market_started(self):
        assert SessionEventType.PRE_MARKET_STARTED.value == "PRE_MARKET_STARTED"

    def test_regular_market_started(self):
        assert SessionEventType.REGULAR_MARKET_STARTED.value == "REGULAR_MARKET_STARTED"

    def test_late_market_started(self):
        assert SessionEventType.LATE_MARKET_STARTED.value == "LATE_MARKET_STARTED"

    def test_new_buy_blocked(self):
        assert SessionEventType.NEW_BUY_BLOCKED_BY_SESSION.value == "NEW_BUY_BLOCKED_BY_SESSION"

    def test_market_closed(self):
        assert SessionEventType.MARKET_CLOSED.value == "MARKET_CLOSED"

    def test_after_market_sync(self):
        assert SessionEventType.AFTER_MARKET_SYNC_STARTED.value == "AFTER_MARKET_SYNC_STARTED"

    def test_eod_triggered(self):
        assert SessionEventType.EOD_TRIGGERED_BY_SESSION.value == "EOD_TRIGGERED_BY_SESSION"

    def test_session_unknown(self):
        assert SessionEventType.SESSION_STATE_UNKNOWN.value == "SESSION_STATE_UNKNOWN"


class TestSessionEvent:
    """SessionEvent 데이터클래스"""

    def test_create_event(self):
        event = SessionEvent(
            event_type=SessionEventType.REGULAR_MARKET_STARTED,
            session_state="REGULAR_MARKET",
            reason="정규장 시작",
        )
        assert event.event_type == SessionEventType.REGULAR_MARKET_STARTED
        assert event.session_state == "REGULAR_MARKET"
        assert event.reason == "정규장 시작"
        assert isinstance(event.timestamp, datetime)

    def test_event_name_property(self):
        event = SessionEvent(
            event_type=SessionEventType.SESSION_STATE_CHANGED,
            session_state="LATE_MARKET",
            reason="장마감 임박",
        )
        assert event.event_name == "SESSION_STATE_CHANGED"

    def test_event_default_timestamp(self):
        before = datetime.now(timezone.utc)
        event = SessionEvent(
            event_type=SessionEventType.TRADING_DAY_CHECKED,
            session_state="CLOSED_HOLIDAY",
            reason="휴장일",
        )
        after = datetime.now(timezone.utc)
        assert before <= event.timestamp <= after

    def test_event_frozen(self):
        event = SessionEvent(
            event_type=SessionEventType.MARKET_CLOSED,
            session_state="CLOSED_AFTER_MARKET",
        )
        with pytest.raises(AttributeError):
            event.session_state = "REGULAR_MARKET"  # type: ignore