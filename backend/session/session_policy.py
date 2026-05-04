"""Session Policy — 세션 상태별 허용 작업 정의"""
from __future__ import annotations

from dataclasses import dataclass
from session.session_state import TradingSessionState


@dataclass(frozen=True)
class SessionPolicy:
    """세션 상태별 허용 작업 정책

    Attributes:
        session_state: 적용된 세션 상태
        allow_scan: 스캐너 실행 허용
        allow_new_buy: 신규매수 허용
        allow_sell: 매도 허용
        allow_cancel: 주문 취소 허용
        allow_sync: 잔고/체결 동기화 허용
        allow_eod: EOD 리포트 실행 허용
        reason: 정책 적용 사유
    """
    session_state: TradingSessionState
    allow_scan: bool
    allow_new_buy: bool
    allow_sell: bool
    allow_cancel: bool
    allow_sync: bool
    allow_eod: bool
    reason: str


# ── 상태별 정책 매핑 ──

_POLICY_MAP: dict[TradingSessionState, SessionPolicy] = {
    TradingSessionState.CLOSED_HOLIDAY: SessionPolicy(
        session_state=TradingSessionState.CLOSED_HOLIDAY,
        allow_scan=False,
        allow_new_buy=False,
        allow_sell=False,
        allow_cancel=False,
        allow_sync=True,
        allow_eod=False,
        reason="휴장일 — 자동매매 미실행",
    ),
    TradingSessionState.CLOSED_BEFORE_MARKET: SessionPolicy(
        session_state=TradingSessionState.CLOSED_BEFORE_MARKET,
        allow_scan=False,
        allow_new_buy=False,
        allow_sell=False,
        allow_cancel=False,
        allow_sync=True,
        allow_eod=False,
        reason="장 시작 전 — 점검/동기화만 가능",
    ),
    TradingSessionState.PRE_MARKET_AUCTION: SessionPolicy(
        session_state=TradingSessionState.PRE_MARKET_AUCTION,
        allow_scan=True,
        allow_new_buy=False,
        allow_sell=False,
        allow_cancel=False,
        allow_sync=True,
        allow_eod=False,
        reason="장전 동시호가 — 관찰만 가능, 신규매수 금지",
    ),
    TradingSessionState.REGULAR_MARKET: SessionPolicy(
        session_state=TradingSessionState.REGULAR_MARKET,
        allow_scan=True,
        allow_new_buy=True,
        allow_sell=True,
        allow_cancel=True,
        allow_sync=True,
        allow_eod=False,
        reason="정규장 — 조건 충족 시 신규매수 가능",
    ),
    TradingSessionState.LATE_MARKET: SessionPolicy(
        session_state=TradingSessionState.LATE_MARKET,
        allow_scan=True,
        allow_new_buy=False,
        allow_sell=True,
        allow_cancel=True,
        allow_sync=True,
        allow_eod=False,
        reason="장 마감 임박 — 신규매수 금지, 보유 종목 관리 중심",
    ),
    TradingSessionState.CLOSING_AUCTION: SessionPolicy(
        session_state=TradingSessionState.CLOSING_AUCTION,
        allow_scan=False,
        allow_new_buy=False,
        allow_sell=True,
        allow_cancel=True,
        allow_sync=True,
        allow_eod=False,
        reason="마감 동시호가 — 신규매수 금지",
    ),
    TradingSessionState.AFTER_MARKET: SessionPolicy(
        session_state=TradingSessionState.AFTER_MARKET,
        allow_scan=False,
        allow_new_buy=False,
        allow_sell=False,
        allow_cancel=False,
        allow_sync=True,
        allow_eod=False,
        reason="장후 시간외 — 동기화만 가능",
    ),
    TradingSessionState.CLOSED_AFTER_MARKET: SessionPolicy(
        session_state=TradingSessionState.CLOSED_AFTER_MARKET,
        allow_scan=False,
        allow_new_buy=False,
        allow_sell=False,
        allow_cancel=False,
        allow_sync=True,
        allow_eod=True,
        reason="장 종료 — EOD 리포트 실행 가능",
    ),
    TradingSessionState.SESSION_STATE_UNKNOWN: SessionPolicy(
        session_state=TradingSessionState.SESSION_STATE_UNKNOWN,
        allow_scan=False,
        allow_new_buy=False,
        allow_sell=False,
        allow_cancel=False,
        allow_sync=False,
        allow_eod=False,
        reason="세션 상태 불명 — 모든 주문 차단",
    ),
}


def get_policy(state: TradingSessionState) -> SessionPolicy:
    """세션 상태에 따른 정책 반환

    Args:
        state: 현재 TradingSessionState

    Returns:
        해당 상태의 SessionPolicy

    Raises:
        KeyError: 정의되지 않은 상태
    """
    if state not in _POLICY_MAP:
        raise KeyError(f"No policy defined for session state: {state}")
    return _POLICY_MAP[state]


def can_new_buy(state: TradingSessionState) -> bool:
    """신규매수 허용 여부 (편의 함수)

    Args:
        state: 현재 TradingSessionState

    Returns:
        신규매수 가능하면 True
    """
    return state not in {
        TradingSessionState.SESSION_STATE_UNKNOWN,
        TradingSessionState.CLOSED_HOLIDAY,
        TradingSessionState.CLOSED_BEFORE_MARKET,
        TradingSessionState.PRE_MARKET_AUCTION,
        TradingSessionState.LATE_MARKET,
        TradingSessionState.CLOSING_AUCTION,
        TradingSessionState.AFTER_MARKET,
        TradingSessionState.CLOSED_AFTER_MARKET,
    }