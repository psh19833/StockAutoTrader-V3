"""Market Clock — KIS 장운영정보 기반 현재 세션 상태 계산

로컬 시간은 보조값으로만 사용하고, KIS API 조회 결과를 기준으로
현재 TradingSessionState를 결정한다.
API 상태와 로컬 시간이 불일치할 때는 안전 우선 처리(UNKNOWN)를 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from session.session_state import TradingSessionState
from session.trading_calendar import TradingCalendarSnapshot


@dataclass(frozen=True)
class MarketSessionSnapshot:
    """장운영정보 스냅샷 — 현재 세션 상태의 완전한 정보

    Attributes:
        trading_day: 오늘 거래일 여부
        session_state: 결정된 세션 상태
        kis_market_status: KIS API가 반환한 원본 장운영 상태 문자열
        local_time: 스냅샷 생성 시각
        api_checked_at: KIS API 조회 시각
        source_endpoints: 참조한 KIS API endpoint 목록
        reason: 상태 결정 사유
    """
    trading_day: bool
    session_state: TradingSessionState
    kis_market_status: str | None = None
    local_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    api_checked_at: datetime | None = None
    source_endpoints: tuple[str, ...] = ()
    reason: str = ""


class MarketClock:
    """KIS 장운영정보 기반 Market Clock

    현재 세션 상태를 KIS API 조회 결과로 계산한다.
    로컬 시간은 보조 확인용으로만 사용.
    """

    def __init__(
        self,
        fetch_market_status_fn: Callable[[], str] | None = None,
    ):
        """
        Args:
            fetch_market_status_fn: KIS 장운영정보 API 호출 함수 (Phase 3+ 연결)
        """
        self._fetch_market_status_fn = fetch_market_status_fn
        self._last_status: str | None = None
        self._last_fetch: datetime | None = None

    def evaluate(
        self,
        calendar_snapshot: TradingCalendarSnapshot,
    ) -> MarketSessionSnapshot:
        """현재 장운영 상태 평가

        Args:
            calendar_snapshot: TradingCalendar에서 확인한 오늘 거래일 정보

        Returns:
            MarketSessionSnapshot 객체
        """
        now = datetime.now(timezone.utc)

        # KIS 장운영정보 API 조회
        kis_status: str | None = None
        api_ok = False

        if self._fetch_market_status_fn is not None:
            try:
                kis_status = self._fetch_market_status_fn()
                self._last_status = kis_status
                self._last_fetch = now
                api_ok = True
            except Exception:
                # API 실패 시 안전 우선 → UNKNOWN
                pass
        else:
            # fetch 함수 미연결
            pass

        # 캘린더 정보 확인
        if not calendar_snapshot.api_available:
            return MarketSessionSnapshot(
                trading_day=False,
                session_state=TradingSessionState.SESSION_STATE_UNKNOWN,
                kis_market_status=kis_status,
                local_time=now,
                api_checked_at=self._last_fetch,
                source_endpoints=calendar_snapshot.source_endpoints,
                reason="Calendar API unavailable — cannot determine session state",
            )

        # 휴장일 처리
        if calendar_snapshot.is_holiday or not calendar_snapshot.is_trading_day:
            return MarketSessionSnapshot(
                trading_day=False,
                session_state=TradingSessionState.CLOSED_HOLIDAY,
                kis_market_status=kis_status,
                local_time=now,
                api_checked_at=self._last_fetch,
                source_endpoints=calendar_snapshot.source_endpoints,
                reason=calendar_snapshot.reason,
            )

        # KIS API 미연결 상태
        if not api_ok and self._fetch_market_status_fn is not None:
            # API는 설정되었지만 실패
            return MarketSessionSnapshot(
                trading_day=True,
                session_state=TradingSessionState.SESSION_STATE_UNKNOWN,
                kis_market_status=kis_status,
                local_time=now,
                api_checked_at=self._last_fetch,
                reason="Market status API failed — safe UNKNOWN",
            )

        # Fetch 함수 미설정 상태 → Phase 2 테스트용 fallback
        if self._fetch_market_status_fn is None:
            return MarketSessionSnapshot(
                trading_day=True,
                session_state=TradingSessionState.REGULAR_MARKET,
                kis_market_status=None,
                local_time=now,
                api_checked_at=None,
                reason="Market clock: fetch function not connected (Phase 2 default)",
            )

        # KIS API 응답 기반 상태 결정
        state = self._resolve_state(kis_status)
        return MarketSessionSnapshot(
            trading_day=True,
            session_state=state,
            kis_market_status=kis_status,
            local_time=now,
            api_checked_at=self._last_fetch,
            source_endpoints=("uapi/domestic-stock/v1/quotations/market-status",),
            reason=f"KIS market status: {kis_status} → {state.value}",
        )

    def _resolve_state(self, kis_status: str | None) -> TradingSessionState:
        """KIS 장운영정보 → TradingSessionState 매핑

        Args:
            kis_status: KIS API가 반환한 장운영 상태 코드

        Returns:
            매핑된 TradingSessionState

        Notes:
            알 수 없는 상태 코드는 SESSION_STATE_UNKNOWN 처리.

        TODO (Phase 3+): LATE_MARKET 시간 기반 전환
        LATE_MARKET은 KIS API 상태 코드만으로 정확히 구분하기 어렵다.
        KIS API가 'STATUS_OPEN'을 반환해도 장 마감 10~15분 전이면
        실질적으로 LATE_MARKET으로 처리해야 한다.
        Phase 3+에서 cutoff 시각(예: 15:20 KST)을 설정 config로 정의하고,
        KIS 상태가 STATUS_OPEN이더라도 현재 로컬 시간이 cutoff를
        지났으면 LATE_MARKET으로 전환하는 로직을 추가할 것.
        cutoff 시각은 환경변수나 설정 파일로 관리해야 하며,
        하드코딩하지 않는다.
        """
        if kis_status is None:
            return TradingSessionState.SESSION_STATE_UNKNOWN

        status_map: dict[str, TradingSessionState] = {
            # KIS 예시 상태 코드 (실제 값은 Phase 3+에서 확정)
            "STATUS_OPEN": TradingSessionState.REGULAR_MARKET,
            "STATUS_PREOPEN": TradingSessionState.PRE_MARKET_AUCTION,
            "STATUS_CLOSEAUCTION": TradingSessionState.CLOSING_AUCTION,
            "STATUS_CLOSE": TradingSessionState.CLOSED_AFTER_MARKET,
            "STATUS_AFTERHOURS": TradingSessionState.AFTER_MARKET,
        }

        # LATE_MARKET은 KIS 상태 + 로컬 시간 보조 확인 필요
        # Phase 3+에서 cutoff 설정 기반 전환 구현 예정
        # 참조: docs/03_PHASE_2_TRADING_SESSION_ENGINE.md (LATE_MARKET 섹션)

        state = status_map.get(kis_status)
        if state is not None:
            return state

        # 알 수 없는 상태 코드
        return TradingSessionState.SESSION_STATE_UNKNOWN

    @staticmethod
    def map_kis_status(kis_status: str, is_trading_day: bool = True) -> TradingSessionState:
        """KIS 장운영정보 → TradingSessionState 매핑 (단축 코드 지원)"""
        if not is_trading_day:
            return TradingSessionState.CLOSED_HOLIDAY
        status_map: dict[str, TradingSessionState] = {
            "OPEN": TradingSessionState.REGULAR_MARKET,
            "STATUS_OPEN": TradingSessionState.REGULAR_MARKET,
            "PREOPEN": TradingSessionState.PRE_MARKET_AUCTION,
            "STATUS_PREOPEN": TradingSessionState.PRE_MARKET_AUCTION,
            "CLOSE": TradingSessionState.CLOSED_AFTER_MARKET,
            "STATUS_CLOSE": TradingSessionState.CLOSED_AFTER_MARKET,
            "STATUS_CLOSEAUCTION": TradingSessionState.CLOSING_AUCTION,
            "STATUS_AFTERHOURS": TradingSessionState.AFTER_MARKET,
        }
        return status_map.get(kis_status, TradingSessionState.SESSION_STATE_UNKNOWN)