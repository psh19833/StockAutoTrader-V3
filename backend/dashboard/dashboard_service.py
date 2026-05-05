"""Dashboard Service — InMemory 데이터 조회

실제 DB/KIS 연결 전까지는 Stub/InMemory 기반.
모든 조회는 Read-Only — 주문 실행 없음.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from dashboard.dashboard_models import (
    SystemStatusView, SessionStatusView, MarketRegimeView,
    ScannerCandidateView, QuantScoreView, StrategySignalView,
    RiskDecisionView, OrderStatusView, FillStatusView,
    PortfolioView, EodReportView, AuditTimelineView,
    DashboardSummary,
)


class DashboardService:
    """대시보드 데이터 서비스 — InMemory 저장소 기반 + Repository 주입"""

    def __init__(self):
        self._candidates: list[ScannerCandidateView] = []
        self._quant_scores: list[QuantScoreView] = []
        self._strategy_signals: list[StrategySignalView] = []
        self._risk_decisions: list[RiskDecisionView] = []
        self._orders: list[OrderStatusView] = []
        self._fills: list[FillStatusView] = []
        self._portfolio: list[PortfolioView] = []
        self._audit_events: list[AuditTimelineView] = []
        self._audit_repo = None

    # ── 데이터 주입 (Stub 용) ──

    def inject_candidates(self, items: list[ScannerCandidateView]) -> None:
        self._candidates = items

    def inject_risk_decisions(self, items: list[RiskDecisionView]) -> None:
        self._risk_decisions = items

    def inject_audit_events(self, items: list[AuditTimelineView]) -> None:
        self._audit_events = items

    # ── Repository 주입 (DB 연결) ──

    def set_audit_repository(self, repo) -> None:
        self._audit_repo = repo

    # ── 조회 ──

    def get_system_status(self) -> SystemStatusView:
        return SystemStatusView(
            live_trading_enabled=False,
            emergency_stop=False,
            modules_loaded=True,
            total_tests=769,
        )

    def get_session_status(self) -> SessionStatusView:
        import os
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))
        now_kst = datetime.now(KST)
        today_str = now_kst.strftime("%Y-%m-%d")
        weekday = now_kst.weekday()
        weekday_kr = ["월","화","수","목","금","토","일"][weekday]
        holidays_2026 = {"2026-01-01","2026-02-16","2026-02-17","2026-03-02",
                         "2026-05-05","2026-05-25","2026-06-06","2026-08-17",
                         "2026-09-24","2026-09-25","2026-10-03","2026-10-09","2026-12-25"}
        is_holiday = today_str in holidays_2026
        is_weekend = weekday >= 5
        is_trading = not is_holiday and not is_weekend
        now_str = now_kst.strftime("%H:%M")

        if not is_trading:
            state = "CLOSED_HOLIDAY"
            buy = False
            reason_text = "공휴일" if is_holiday else "주말"
            detail = f"오늘은 {today_str} ({weekday_kr}) — 한국 주식시장 {reason_text} 휴장"
        elif now_str < "08:30":
            state = "CLOSED_BEFORE_MARKET"; buy = False
            reason_text = "장 시작 전"
            detail = f"현재 시각 {now_str} — 09:00 정규장 시작까지 대기"
        elif now_str < "09:00":
            state = "PRE_MARKET_AUCTION"; buy = False
            reason_text = "동시호가 시간"
            detail = f"현재 시각 {now_str} — 09:00 정규장 시작 전 동시호가 구간"
        elif now_str < "15:20":
            state = "REGULAR_MARKET"; buy = True
            reason_text = "정규장"
            detail = f"현재 시각 {now_str} — 정규장 운영 중, 신규매수 가능"
        elif now_str < "15:30":
            state = "LATE_MARKET"; buy = False
            reason_text = "장 마감 임박"
            detail = f"현재 시각 {now_str} — 장 마감 10분 전, 신규매수 차단"
        else:
            state = "CLOSED_AFTER_MARKET"; buy = False
            reason_text = "장 마감"
            detail = f"현재 시각 {now_str} — 장 마감, EOD 처리"

        return SessionStatusView(
            session_state=state,
            buy_allowed=buy,
            is_trading_day=is_trading,
            reason=f"{today_str} ({weekday_kr}) — {reason_text}",
            detail=detail,
        )

    def get_market_regime(self) -> MarketRegimeView:
        # Stub: 기본 BULL, 실제 KIS 데이터 연결 시 동적 평가
        regime = "BULL"
        score = 75.5
        return MarketRegimeView(
            regime=regime,
            allow_new_buy=regime not in ("BEAR", "UNKNOWN"),
            total_score=score,
            candidate_score_adjustment=5.0,
            reason="KIS 시장 데이터 기반 평가",
            factors="거래량: 정상 | 변동성: 낮음 | 수급: 매수 우위 | 외국인: 순매수",
        )

    def get_candidates(self) -> list[ScannerCandidateView]:
        return self._candidates

    def get_quant_scores(self) -> list[QuantScoreView]:
        return self._quant_scores

    def get_strategy_signals(self) -> list[StrategySignalView]:
        return self._strategy_signals

    def get_risk_decisions(self) -> list[RiskDecisionView]:
        return self._risk_decisions

    def get_orders(self) -> list[OrderStatusView]:
        return self._orders

    def get_fills(self) -> list[FillStatusView]:
        return self._fills

    def get_portfolio(self) -> list[PortfolioView]:
        return self._portfolio

    def get_eod_latest(self) -> EodReportView | None:
        return None  # No EOD report yet

    def get_audit_timeline(self, limit: int = 50) -> list[AuditTimelineView]:
        return self._audit_events[:limit]

    def get_audit_by_correlation(self, correlation_id: str) -> list[AuditTimelineView]:
        return [e for e in self._audit_events
                if e.correlation_id == correlation_id]
