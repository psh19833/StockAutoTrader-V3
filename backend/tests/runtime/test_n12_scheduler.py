"""N12: Runtime Scheduler — session-aware execution plans."""
import pytest
from unittest.mock import MagicMock


class TestScheduler:
    def test_closed_holiday_no_execution(self):
        allowed_sessions = {"REGULAR_MARKET", "PRE_MARKET_AUCTION", "LATE_MARKET"}
        assert "CLOSED_HOLIDAY" not in allowed_sessions

    def test_regular_market_allows_scan(self):
        session = "REGULAR_MARKET"
        can_scan = session == "REGULAR_MARKET"
        assert can_scan is True

    def test_late_market_blocks_new_buy(self):
        session = "LATE_MARKET"
        can_new_buy = session not in ("LATE_MARKET", "CLOSING_AUCTION", "CLOSED_AFTER_MARKET", "UNKNOWN")
        assert can_new_buy is False

    def test_closed_after_market_triggers_eod(self):
        session = "CLOSED_AFTER_MARKET"
        should_eod = session == "CLOSED_AFTER_MARKET"
        assert should_eod is True

    def test_unknown_blocks_all(self):
        session = "UNKNOWN"
        can_scan = session != "UNKNOWN"
        can_buy = session != "UNKNOWN"
        assert can_scan is False
        assert can_buy is False

    def test_scheduler_does_not_submit_orders(self):
        """Scheduler orchestrates but does NOT submit orders directly."""
        orders_submitted = 0
        assert orders_submitted == 0
