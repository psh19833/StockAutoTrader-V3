"""Session Guard — 주문 전 세션 검증

실제 주문 실행 전에 세션 상태를 확인하여 주문 가능 여부를 판단한다.
실제 주문 실행은 구현하지 않으며, 검증 결과만 반환한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from session.session_state import TradingSessionState
from session.session_policy import SessionPolicy, get_policy


class GuardDecision(str, Enum):
    """검증 결과"""
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class NewBuyBlockCode(str, Enum):
    """신규매수 차단 사유 코드"""
    SESSION_CLOSED_HOLIDAY = "SESSION_CLOSED_HOLIDAY"
    SESSION_BEFORE_MARKET = "SESSION_BEFORE_MARKET"
    SESSION_PRE_MARKET_AUCTION = "SESSION_PRE_MARKET_AUCTION"
    SESSION_LATE_MARKET_BUY_BLOCKED = "SESSION_LATE_MARKET_BUY_BLOCKED"
    SESSION_CLOSING_AUCTION = "SESSION_CLOSING_AUCTION"
    SESSION_AFTER_MARKET = "SESSION_AFTER_MARKET"
    SESSION_CLOSED_AFTER_MARKET = "SESSION_CLOSED_AFTER_MARKET"
    SESSION_STATE_UNKNOWN = "SESSION_STATE_UNKNOWN"
    SESSION_API_UNAVAILABLE = "SESSION_API_UNAVAILABLE"


# 차단 코드와 세션 상태 매핑
_BLOCK_CODE_MAP: dict[TradingSessionState, NewBuyBlockCode] = {
    TradingSessionState.CLOSED_HOLIDAY: NewBuyBlockCode.SESSION_CLOSED_HOLIDAY,
    TradingSessionState.CLOSED_BEFORE_MARKET: NewBuyBlockCode.SESSION_BEFORE_MARKET,
    TradingSessionState.PRE_MARKET_AUCTION: NewBuyBlockCode.SESSION_PRE_MARKET_AUCTION,
    TradingSessionState.LATE_MARKET: NewBuyBlockCode.SESSION_LATE_MARKET_BUY_BLOCKED,
    TradingSessionState.CLOSING_AUCTION: NewBuyBlockCode.SESSION_CLOSING_AUCTION,
    TradingSessionState.AFTER_MARKET: NewBuyBlockCode.SESSION_AFTER_MARKET,
    TradingSessionState.CLOSED_AFTER_MARKET: NewBuyBlockCode.SESSION_CLOSED_AFTER_MARKET,
    TradingSessionState.SESSION_STATE_UNKNOWN: NewBuyBlockCode.SESSION_STATE_UNKNOWN,
}


@dataclass(frozen=True)
class SessionGuardResult:
    """세션 검증 결과

    Attributes:
        decision: ALLOWED 또는 BLOCKED
        block_code: 차단된 경우 차단 사유 코드 (None if ALLOWED)
        reason: 상세 사유
        session_state: 검증 당시 세션 상태
    """
    decision: GuardDecision
    block_code: NewBuyBlockCode | None = None
    reason: str = ""
    session_state: TradingSessionState = TradingSessionState.SESSION_STATE_UNKNOWN

    @property
    def is_allowed(self) -> bool:
        return self.decision == GuardDecision.ALLOWED

    @property
    def is_blocked(self) -> bool:
        return self.decision == GuardDecision.BLOCKED


class SessionGuard:
    """세션 상태 기반 주문 검증기

    신규매수 전 이 Guard를 통해 세션 상태를 확인한다.
    """

    def check_new_buy(
        self,
        state: TradingSessionState,
        policy: SessionPolicy | None = None,
    ) -> SessionGuardResult:
        """신규매수 허용 여부 검증

        Args:
            state: 현재 세션 상태
            policy: 정책 객체 (None이면 get_policy()로 자동 조회)

        Returns:
            SessionGuardResult — ALLOWED 또는 BLOCKED
        """
        if policy is None:
            policy = get_policy(state)

        if policy.allow_new_buy:
            return SessionGuardResult(
                decision=GuardDecision.ALLOWED,
                session_state=state,
                reason=policy.reason,
            )

        block_code = _BLOCK_CODE_MAP.get(state, NewBuyBlockCode.SESSION_STATE_UNKNOWN)

        return SessionGuardResult(
            decision=GuardDecision.BLOCKED,
            block_code=block_code,
            session_state=state,
            reason=policy.reason,
        )