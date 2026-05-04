"""TradingSessionState — SAT3 시장 세션 상태 모델"""
from __future__ import annotations

from enum import Enum


class TradingSessionState(str, Enum):
    """KIS 장운영정보 기반 시장 세션 상태

    모든 상태는 KIS API 조회 결과를 기준으로 결정된다.
    로컬 시간만으로 이 상태를 판단하지 않는다.
    """

    # ── 휴장 ──
    CLOSED_HOLIDAY = "CLOSED_HOLIDAY"
    """휴장일. 자동매매 미실행."""

    CLOSED_BEFORE_MARKET = "CLOSED_BEFORE_MARKET"
    """거래일이지만 장 시작 전. 점검/동기화 가능, 신규매수 금지."""

    # ── 장전 ──
    PRE_MARKET_AUCTION = "PRE_MARKET_AUCTION"
    """장전 동시호가/예상체결 구간. 관찰 가능, 신규매수 금지."""

    # ── 정규장 ──
    REGULAR_MARKET = "REGULAR_MARKET"
    """정규장. 조건 충족 시 신규매수 가능."""

    # ── 장마감 임박 ──
    LATE_MARKET = "LATE_MARKET"
    """장 마감 임박 구간. 신규매수 금지, 보유 종목 관리 중심."""

    # ── 마감 동시호가 ──
    CLOSING_AUCTION = "CLOSING_AUCTION"
    """장마감 동시호가. 신규매수 금지, 정책에 따라 청산만 허용 가능."""

    # ── 장후 ──
    AFTER_MARKET = "AFTER_MARKET"
    """장후 시간외. 기본 자동매매 금지, 체결/잔고 동기화 가능."""

    # ── 장 종료 ──
    CLOSED_AFTER_MARKET = "CLOSED_AFTER_MARKET"
    """장 종료 후. EOD 리포트 가능, 신규 주문 금지."""

    # ── 불명 ──
    SESSION_STATE_UNKNOWN = "SESSION_STATE_UNKNOWN"
    """API 실패 또는 상태 불명. 신규 주문 차단."""


# 편의 상수: 매수 불가 상태 집합
BUY_BLOCKED_STATES: frozenset[TradingSessionState] = frozenset({
    TradingSessionState.CLOSED_HOLIDAY,
    TradingSessionState.CLOSED_BEFORE_MARKET,
    TradingSessionState.PRE_MARKET_AUCTION,
    TradingSessionState.LATE_MARKET,
    TradingSessionState.CLOSING_AUCTION,
    TradingSessionState.AFTER_MARKET,
    TradingSessionState.CLOSED_AFTER_MARKET,
    TradingSessionState.SESSION_STATE_UNKNOWN,
})

# 편의 상수: 매수 허용 상태 집합
BUY_ALLOWED_STATES: frozenset[TradingSessionState] = frozenset({
    TradingSessionState.REGULAR_MARKET,
})