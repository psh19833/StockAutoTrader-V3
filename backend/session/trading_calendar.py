"""Trading Calendar — KIS 국내휴장일조회 기반 거래일 판단

SAT3의 거래일/휴장일 판단은 반드시 KIS API 조회 결과를 기준으로 한다.
로컬 시간/달력만으로 판단하지 않으며, API 실패 시 추정하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable


@dataclass(frozen=True)
class TradingCalendarSnapshot:
    """거래일 캘린더 스냅샷

    KIS 국내휴장일조회 API 결과를 기반으로 한 당일 거래일 정보.
    """

    reference_date: date
    is_trading_day: bool
    is_holiday: bool
    holidays: tuple[date, ...] = field(default_factory=tuple)
    source_endpoints: tuple[str, ...] = field(default_factory=tuple)
    next_trading_day: date | None = None
    api_checked_at: datetime | None = None
    api_available: bool = False
    reason: str = ""

    @property
    def is_available(self) -> bool:
        """API 조회 성공 여부"""
        return self.api_available


class TradingCalendar:
    """KIS 국내휴장일조회 기반 Trading Calendar

    거래일 판단 구조와 인터페이스 제공.
    실제 API 호출은 Phase 3+에서 fetch 함수를 연결하여 사용.

    주요 원칙:
    - 오늘 거래일 여부는 KIS API로 확인
    - API 실패 시 임의 추정 금지 → api_available=False
    - DataUnavailable 우선 처리
    """

    def __init__(
        self,
        fetch_holidays_fn: Callable[[], tuple[date, ...]] | None = None,
    ):
        """
        Args:
            fetch_holidays_fn: KIS 국내휴장일조회 API 호출 함수 (Phase 3+ 연결)
        """
        self._fetch_holidays_fn = fetch_holidays_fn
        self._holidays: tuple[date, ...] = ()
        self._last_fetch: datetime | None = None

    def check_today(self) -> TradingCalendarSnapshot:
        """오늘 거래일 확인

        Returns:
            TradingCalendarSnapshot 객체

        Notes:
            fetch_holidays_fn이 설정되지 않은 경우 api_available=False 반환
            (실제 API 연결 전까지는 Unknown 상태로 처리)
        """
        return self._check_date(date.today())

    def check_date(self, target: date) -> TradingCalendarSnapshot:
        """특정 날짜의 거래일 확인

        Args:
            target: 확인할 날짜

        Returns:
            TradingCalendarSnapshot 객체
        """
        return self._check_date(target)

    def _check_date(self, target: date) -> TradingCalendarSnapshot:
        """내부 날짜 확인 로직"""
        now = datetime.now(timezone.utc)

        # fetch 함수가 없으면 API 미연결 상태
        if self._fetch_holidays_fn is None:
            return TradingCalendarSnapshot(
                reference_date=target,
                is_trading_day=False,
                is_holiday=False,
                api_checked_at=now,
                api_available=False,
                reason="KIS holiday API not connected. Use fetch_holidays_fn to connect.",
            )

        try:
            self._holidays = self._fetch_holidays_fn()
            self._last_fetch = now
        except Exception as e:
            # API 실패 시 추정 금지 → api_available=False
            return TradingCalendarSnapshot(
                reference_date=target,
                is_trading_day=False,
                is_holiday=False,
                holidays=self._holidays,
                api_checked_at=now,
                api_available=False,
                reason=f"Holiday API fetch failed: {e}",
            )

        is_holiday = target in self._holidays
        # 평일(월-금)이면서 휴장일 목록에 없으면 거래일
        is_weekend = target.weekday() >= 5  # 5=토, 6=일
        is_trading_day = not is_holiday and not is_weekend

        # 다음 거래일 계산
        next_day = self._calc_next_trading_day(target)

        if is_holiday:
            reason = f"휴장일 (KIS holiday list)"
        elif is_weekend:
            reason = f"주말 ({target.strftime('%A')})"
        else:
            reason = "거래일"

        return TradingCalendarSnapshot(
            reference_date=target,
            is_trading_day=is_trading_day,
            is_holiday=is_holiday or is_weekend,
            holidays=self._holidays,
            next_trading_day=next_day,
            api_checked_at=now,
            api_available=True,
            reason=reason,
        )

    def _calc_next_trading_day(self, from_date: date) -> date | None:
        """from_date 기준 다음 거래일 계산

        휴장일 목록과 주말을 고려하여 다음 거래일을 찾는다.
        """
        if not self._holidays:
            return None
        candidate = from_date
        for _ in range(365):  # 최대 1년
            candidate = candidate.__add__(__import__("datetime").timedelta(days=1))
            if candidate.weekday() >= 5:
                continue
            if candidate in self._holidays:
                continue
            return candidate
        return None