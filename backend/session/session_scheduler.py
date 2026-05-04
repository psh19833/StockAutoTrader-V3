"""Session Scheduler — 세션 상태 기반 작업 계획

Phase 2에서는 실제 백그라운드 스케줄러 실행을 구현하지 않고,
세션 상태에 따라 어떤 작업이 예정되어야 하는지 계획 객체로만 표현한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from session.session_state import TradingSessionState
from session.session_events import SessionEventType
from session.session_policy import get_policy


class ScheduledAction(str, Enum):
    """예약 가능한 작업 유형"""
    NEW_BUY = "NEW_BUY"
    SELL = "SELL"
    CANCEL = "CANCEL"
    SCAN = "SCAN"
    SYNC = "SYNC"
    MONITOR = "MONITOR"
    EOD = "EOD"
    NONE = "NONE"


@dataclass(frozen=True)
class SchedulePlan:
    """세션 상태별 실행 계획

    Attributes:
        session_state: 기준 세션 상태
        scheduled_actions: 예정된 작업 목록
        generated_at: 계획 생성 시각
        description: 계획 설명
    """
    session_state: TradingSessionState
    scheduled_actions: tuple[ScheduledAction, ...] = field(default_factory=tuple)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""

    @property
    def has_actions(self) -> bool:
        return len(self.scheduled_actions) > 0


# 상태별 예약 작업 정의
_ACTION_PLAN: dict[TradingSessionState, tuple[ScheduledAction, ...]] = {
    TradingSessionState.CLOSED_HOLIDAY: (ScheduledAction.SYNC,),
    TradingSessionState.CLOSED_BEFORE_MARKET: (ScheduledAction.SYNC,),
    TradingSessionState.PRE_MARKET_AUCTION: (ScheduledAction.MONITOR, ScheduledAction.SYNC),
    TradingSessionState.REGULAR_MARKET: (
        ScheduledAction.SCAN,
        ScheduledAction.MONITOR,
        ScheduledAction.NEW_BUY,
        ScheduledAction.SELL,
        ScheduledAction.CANCEL,
        ScheduledAction.SYNC,
    ),
    TradingSessionState.LATE_MARKET: (
        ScheduledAction.MONITOR,
        ScheduledAction.SELL,
        ScheduledAction.CANCEL,
        ScheduledAction.SYNC,
    ),
    TradingSessionState.CLOSING_AUCTION: (ScheduledAction.SELL, ScheduledAction.CANCEL, ScheduledAction.SYNC),
    TradingSessionState.AFTER_MARKET: (ScheduledAction.SYNC,),
    TradingSessionState.CLOSED_AFTER_MARKET: (ScheduledAction.SYNC, ScheduledAction.EOD),
    TradingSessionState.SESSION_STATE_UNKNOWN: (),
}


class SessionScheduler:
    """세션 상태 기반 작업 계획 생성기

    Phase 2: 계획 객체 수준까지만 구현.
    실제 백그라운드 스케줄러 실행은 Phase 8+에서 구현.
    """

    def plan(
        self,
        state: TradingSessionState,
        generated_at: datetime | None = None,
    ) -> SchedulePlan:
        """현재 세션 상태에 따른 작업 계획 생성

        Args:
            state: 현재 세션 상태
            generated_at: 계획 생성 시각 (기본: 현재)

        Returns:
            SchedulePlan 객체
        """
        actions = _ACTION_PLAN.get(state, ())
        policy = get_policy(state)

        # 정책 기반 설명
        if state == TradingSessionState.SESSION_STATE_UNKNOWN:
            desc = "세션 상태 불명 — 예약된 작업 없음"
        elif state == TradingSessionState.REGULAR_MARKET:
            desc = "정규장 — 전체 작업 허용"
        elif state == TradingSessionState.LATE_MARKET:
            desc = "장 마감 임박 — 매수 제외"
        elif state == TradingSessionState.CLOSED_HOLIDAY:
            desc = "휴장일 — 동기화만"
        elif state == TradingSessionState.CLOSED_AFTER_MARKET:
            desc = "장 종료 — EOD 준비"
        else:
            desc = policy.reason

        return SchedulePlan(
            session_state=state,
            scheduled_actions=actions,
            generated_at=generated_at or datetime.now(timezone.utc),
            description=desc,
        )