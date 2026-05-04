"""Session-aware SAT3 Runtime Scheduler (N12)."""
from __future__ import annotations

from enum import Enum
from typing import Optional


class SessionState(Enum):
    CLOSED_HOLIDAY = "CLOSED_HOLIDAY"
    CLOSED_BEFORE_MARKET = "CLOSED_BEFORE_MARKET"
    PRE_MARKET_AUCTION = "PRE_MARKET_AUCTION"
    REGULAR_MARKET = "REGULAR_MARKET"
    LATE_MARKET = "LATE_MARKET"
    CLOSING_AUCTION = "CLOSING_AUCTION"
    CLOSED_AFTER_MARKET = "CLOSED_AFTER_MARKET"
    UNKNOWN = "UNKNOWN"


SCAN_ALLOWED = {SessionState.REGULAR_MARKET}
EVALUATE_ALLOWED = {SessionState.REGULAR_MARKET}
NEW_BUY_ALLOWED = {SessionState.REGULAR_MARKET}
EOD_ALLOWED = {SessionState.CLOSED_AFTER_MARKET}
PREPARE_ALLOWED = {SessionState.CLOSED_BEFORE_MARKET, SessionState.PRE_MARKET_AUCTION}


class Scheduler:
    """Session-aware task planner."""

    def __init__(self):
        self._session = SessionState.UNKNOWN

    def set_session(self, session: SessionState) -> None:
        self._session = session

    def get_session(self) -> SessionState:
        return self._session

    def can_scan(self) -> bool:
        return self._session in SCAN_ALLOWED

    def can_evaluate(self) -> bool:
        return self._session in EVALUATE_ALLOWED

    def can_new_buy(self) -> bool:
        return self._session in NEW_BUY_ALLOWED

    def should_eod(self) -> bool:
        return self._session in EOD_ALLOWED

    def should_prepare(self) -> bool:
        return self._session in PREPARE_ALLOWED

    def get_task_plan(self) -> list[str]:
        """Return ordered list of tasks for current session."""
        tasks = []
        if self._session == SessionState.UNKNOWN:
            return ["BLOCK_ALL"]
        if self._session == SessionState.CLOSED_HOLIDAY:
            return ["NOOP"]
        if self.should_prepare():
            tasks.append("PREPARE_DATA")
        if self.can_scan():
            tasks.extend(["SCAN", "EVALUATE", "RISK_CHECK"])
        if self.should_eod():
            tasks.extend(["EOD_REPORT", "TELEGRAM_NOTIFY"])
        return tasks
