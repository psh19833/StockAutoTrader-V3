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
    """대시보드 데이터 서비스 — InMemory 저장소 기반"""

    def __init__(self):
        self._candidates: list[ScannerCandidateView] = []
        self._quant_scores: list[QuantScoreView] = []
        self._strategy_signals: list[StrategySignalView] = []
        self._risk_decisions: list[RiskDecisionView] = []
        self._orders: list[OrderStatusView] = []
        self._fills: list[FillStatusView] = []
        self._portfolio: list[PortfolioView] = []
        self._audit_events: list[AuditTimelineView] = []

    # ── 데이터 주입 (Stub 용) ──

    def inject_candidates(self, items: list[ScannerCandidateView]) -> None:
        self._candidates = items

    def inject_risk_decisions(self, items: list[RiskDecisionView]) -> None:
        self._risk_decisions = items

    def inject_audit_events(self, items: list[AuditTimelineView]) -> None:
        self._audit_events = items

    # ── 조회 ──

    def get_system_status(self) -> SystemStatusView:
        return SystemStatusView(
            live_trading_enabled=False,
            emergency_stop=False,
            modules_loaded=True,
            total_tests=769,
        )

    def get_session_status(self) -> SessionStatusView:
        return SessionStatusView(
            session_state="REGULAR_MARKET",
            buy_allowed=True,
            is_trading_day=True,
        )

    def get_market_regime(self) -> MarketRegimeView:
        return MarketRegimeView(
            regime="BULL",
            allow_new_buy=True,
            total_score=75.5,
            candidate_score_adjustment=5.0,
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
