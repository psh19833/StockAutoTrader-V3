"""Phase 2 — Trading Calendar / Market Clock / Session Guard / Scheduler 단위 테스트"""
import pytest
from datetime import date, datetime, timezone
from session.session_state import TradingSessionState, BUY_BLOCKED_STATES, BUY_ALLOWED_STATES
from session.trading_calendar import TradingCalendar, TradingCalendarSnapshot
from session.market_clock import MarketClock, MarketSessionSnapshot
from session.session_guard import (
    SessionGuard,
    SessionGuardResult,
    GuardDecision,
    NewBuyBlockCode,
)
from session.session_scheduler import SessionScheduler, ScheduledAction, SchedulePlan


# ── Trading Calendar Tests ──

class TestTradingCalendar:
    """TradingCalendar 기본"""

    def test_no_fetch_fn_returns_unavailable(self):
        """fetch 함수 없으면 api_available=False"""
        cal = TradingCalendar()
        snap = cal.check_today()
        assert snap.api_available is False
        assert snap.is_trading_day is False

    def test_holiday_list_makes_holiday(self):
        """KIS 휴장일 목록에 있으면 휴장일"""
        holidays = (date(2026, 5, 5), date(2026, 5, 6))
        def fetch():
            return holidays
        cal = TradingCalendar(fetch_holidays_fn=fetch)
        snap = cal.check_date(date(2026, 5, 5))
        assert snap.is_holiday is True
        assert snap.is_trading_day is False
        assert snap.api_available is True

    def test_weekday_not_holiday_is_trading_day(self):
        """평일이면서 휴장일이 아니면 거래일"""
        holidays = (date(2026, 5, 5),)
        def fetch():
            return holidays
        cal = TradingCalendar(fetch_holidays_fn=fetch)
        # 2026-05-07 (목요일) — 휴장일 아님
        snap = cal.check_date(date(2026, 5, 7))
        assert snap.is_trading_day is True
        assert snap.is_holiday is False

    def test_weekend_is_holiday(self):
        """주말은 휴장일"""
        holidays = ()
        def fetch():
            return holidays
        cal = TradingCalendar(fetch_holidays_fn=fetch)
        # 2026-05-09 (토요일)
        snap = cal.check_date(date(2026, 5, 9))
        assert snap.is_trading_day is False
        assert snap.is_holiday is True

    def test_fetch_failure_returns_unavailable(self):
        """API 실패 시 api_available=False, 추정 금지"""
        def fetch():
            raise RuntimeError("KIS API connection failed")
        cal = TradingCalendar(fetch_holidays_fn=fetch)
        snap = cal.check_today()
        assert snap.api_available is False
        assert snap.is_trading_day is False  # 추정 금지

    def test_next_trading_day_calculated(self):
        """다음 거래일 계산"""
        holidays = (date(2026, 5, 8),)
        def fetch():
            return holidays
        cal = TradingCalendar(fetch_holidays_fn=fetch)
        # 2026-05-06 (수) → 다음 거래일: 2026-05-07 (목)
        snap = cal.check_date(date(2026, 5, 6))
        assert snap.next_trading_day == date(2026, 5, 7)

    def test_check_date_specific(self):
        """특정 날짜 확인"""
        holidays = (date(2026, 12, 25),)
        def fetch():
            return holidays
        cal = TradingCalendar(fetch_holidays_fn=fetch)
        snap = cal.check_date(date(2026, 12, 25))
        assert snap.is_holiday is True


# ── Market Clock Tests ──

class TestMarketClock:
    """MarketClock 기본"""

    _WEEKDAY = date(2026, 5, 7)  # Thursday

    def _weekday_calendar(self, fetch_holidays_fn):
        cal = TradingCalendar(fetch_holidays_fn=fetch_holidays_fn)
        return cal.check_date(self._WEEKDAY)

    def test_no_fetch_fn_no_calendar_unknown(self):
        """fetch 함수 없고 캘린더 없으면 기본 REGULAR_MARKET (Phase 2 default)"""
        clock = MarketClock()
        cal = TradingCalendar()
        snap = clock.evaluate(cal.check_today())
        # 캘린더 API 미연결 → UNKNOWN
        assert snap.session_state == TradingSessionState.SESSION_STATE_UNKNOWN

    def test_holiday_returns_closed_holiday(self):
        """휴장일이면 CLOSED_HOLIDAY"""
        def fetch_holidays():
            return (date.today(),)
        cal = TradingCalendar(fetch_holidays_fn=fetch_holidays)
        clock = MarketClock()
        snap = clock.evaluate(cal.check_today())
        assert snap.session_state == TradingSessionState.CLOSED_HOLIDAY
        assert snap.trading_day is False

    def test_api_failure_returns_unknown(self):
        """KIS 상태 API 실패 시 UNKNOWN"""
        def fetch_holidays():
            return ()
        def fetch_status():
            raise RuntimeError("Market status API timeout")
        clock = MarketClock(fetch_market_status_fn=fetch_status)
        snap = clock.evaluate(self._weekday_calendar(fetch_holidays))
        assert snap.session_state == TradingSessionState.SESSION_STATE_UNKNOWN

    def test_known_status_maps_correctly(self):
        """KIS 상태 코드가 정상 매핑"""
        def fetch_holidays():
            return ()
        def fetch_status():
            return "STATUS_OPEN"
        clock = MarketClock(fetch_market_status_fn=fetch_status)
        snap = clock.evaluate(self._weekday_calendar(fetch_holidays))
        assert snap.session_state == TradingSessionState.REGULAR_MARKET
        assert snap.kis_market_status == "STATUS_OPEN"

    def test_preopen_status_maps(self):
        """STATUS_PREOPEN → PRE_MARKET_AUCTION"""
        def fetch_holidays():
            return ()
        def fetch_status():
            return "STATUS_PREOPEN"
        clock = MarketClock(fetch_market_status_fn=fetch_status)
        snap = clock.evaluate(self._weekday_calendar(fetch_holidays))
        assert snap.session_state == TradingSessionState.PRE_MARKET_AUCTION

    def test_close_auction_status_maps(self):
        """STATUS_CLOSEAUCTION → CLOSING_AUCTION"""
        def fetch_holidays():
            return ()
        def fetch_status():
            return "STATUS_CLOSEAUCTION"
        clock = MarketClock(fetch_market_status_fn=fetch_status)
        snap = clock.evaluate(self._weekday_calendar(fetch_holidays))
        assert snap.session_state == TradingSessionState.CLOSING_AUCTION

    def test_afterhours_status_maps(self):
        """STATUS_AFTERHOURS → AFTER_MARKET"""
        def fetch_holidays():
            return ()
        def fetch_status():
            return "STATUS_AFTERHOURS"
        clock = MarketClock(fetch_market_status_fn=fetch_status)
        snap = clock.evaluate(self._weekday_calendar(fetch_holidays))
        assert snap.session_state == TradingSessionState.AFTER_MARKET

    def test_unknown_status_maps_to_unknown(self):
        """알 수 없는 상태 코드 → SESSION_STATE_UNKNOWN"""
        def fetch_holidays():
            return ()
        def fetch_status():
            return "STATUS_UNKNOWN_CODE_XXX"
        clock = MarketClock(fetch_market_status_fn=fetch_status)
        snap = clock.evaluate(self._weekday_calendar(fetch_holidays))
        assert snap.session_state == TradingSessionState.SESSION_STATE_UNKNOWN


# ── Session Guard Tests ──

class TestSessionGuard:
    """SessionGuard — 주문 전 세션 검증"""

    def test_regular_market_allows_new_buy(self):
        """REGULAR_MARKET에서 신규매수 허용"""
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.REGULAR_MARKET)
        assert result.decision == GuardDecision.ALLOWED
        assert result.block_code is None

    def test_closed_holiday_blocks_new_buy(self):
        """CLOSED_HOLIDAY에서 신규매수 차단"""
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.CLOSED_HOLIDAY)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_CLOSED_HOLIDAY

    def test_late_market_blocks_new_buy(self):
        """LATE_MARKET에서 신규매수 차단"""
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.LATE_MARKET)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_LATE_MARKET_BUY_BLOCKED

    def test_session_unknown_blocks_new_buy(self):
        """SESSION_STATE_UNKNOWN에서 신규매수 차단"""
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.SESSION_STATE_UNKNOWN)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_STATE_UNKNOWN

    def test_closed_before_market_blocks(self):
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.CLOSED_BEFORE_MARKET)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_BEFORE_MARKET

    def test_pre_market_auction_blocks(self):
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.PRE_MARKET_AUCTION)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_PRE_MARKET_AUCTION

    def test_closing_auction_blocks(self):
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.CLOSING_AUCTION)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_CLOSING_AUCTION

    def test_after_market_blocks(self):
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.AFTER_MARKET)
        assert result.decision == GuardDecision.BLOCKED

    def test_closed_after_market_blocks(self):
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.CLOSED_AFTER_MARKET)
        assert result.decision == GuardDecision.BLOCKED

    def test_check_with_explicit_policy_overrides(self):
        """정책 오버라이드로 검증"""
        guard = SessionGuard()
        from session.session_policy import get_policy
        policy = get_policy(TradingSessionState.REGULAR_MARKET)
        result = guard.check_new_buy(TradingSessionState.REGULAR_MARKET, policy=policy)
        assert result.decision == GuardDecision.ALLOWED

    def test_local_time_only_does_not_allow(self):
        """로컬 시간만으로는 주문을 허용하지 않음 — Guard가 검증"""
        guard = SessionGuard()
        # 유저가 로컬 시간이 장중이라고 주장해도 UNKNOWN 차단
        result = guard.check_new_buy(TradingSessionState.SESSION_STATE_UNKNOWN)
        assert result.decision == GuardDecision.BLOCKED
        assert result.block_code == NewBuyBlockCode.SESSION_STATE_UNKNOWN

    def test_result_includes_reason(self):
        guard = SessionGuard()
        result = guard.check_new_buy(TradingSessionState.SESSION_STATE_UNKNOWN)
        assert result.reason is not None
        assert len(result.reason) > 0


# ── Session Scheduler Tests ──

class TestSessionScheduler:
    """SessionScheduler — 예약 작업 계획"""

    def test_schedule_plan_created(self):
        """스케줄 계획 생성"""
        scheduler = SessionScheduler()
        plan = scheduler.plan(TradingSessionState.REGULAR_MARKET)
        assert isinstance(plan, SchedulePlan)
        assert plan.session_state == TradingSessionState.REGULAR_MARKET

    def test_regular_market_has_scan_and_monitor(self):
        """REGULAR_MARKET에서 스캔 및 모니터링 예정"""
        scheduler = SessionScheduler()
        plan = scheduler.plan(TradingSessionState.REGULAR_MARKET)
        actions = set(plan.scheduled_actions)
        assert ScheduledAction.SCAN in actions
        assert ScheduledAction.MONITOR in actions

    def test_late_market_has_no_buy_actions(self):
        """LATE_MARKET에서 매수 관련 작업 없음"""
        scheduler = SessionScheduler()
        plan = scheduler.plan(TradingSessionState.LATE_MARKET)
        actions = set(plan.scheduled_actions)
        assert ScheduledAction.NEW_BUY not in actions

    def test_closed_holiday_has_only_sync(self):
        """CLOSED_HOLIDAY에서 동기화만 예정"""
        scheduler = SessionScheduler()
        plan = scheduler.plan(TradingSessionState.CLOSED_HOLIDAY)
        actions = set(plan.scheduled_actions)
        assert ScheduledAction.NEW_BUY not in actions
        assert ScheduledAction.SCAN not in actions
        assert ScheduledAction.SYNC in actions

    def test_session_unknown_has_no_actions(self):
        """SESSION_STATE_UNKNOWN에서 작업 없음"""
        scheduler = SessionScheduler()
        plan = scheduler.plan(TradingSessionState.SESSION_STATE_UNKNOWN)
        assert len(plan.scheduled_actions) == 0

    def test_eod_scheduled_in_closed_after_market(self):
        """CLOSED_AFTER_MARKET에서 EOD 예정"""
        scheduler = SessionScheduler()
        plan = scheduler.plan(TradingSessionState.CLOSED_AFTER_MARKET)
        actions = set(plan.scheduled_actions)
        assert ScheduledAction.EOD in actions

    def test_plan_has_snapshot_info(self):
        """SchedulePlan에 현재 상태 정보 포함"""
        scheduler = SessionScheduler()
        now = datetime.now(timezone.utc)
        plan = scheduler.plan(TradingSessionState.REGULAR_MARKET, generated_at=now)
        assert plan.generated_at == now
        assert plan.session_state == TradingSessionState.REGULAR_MARKET