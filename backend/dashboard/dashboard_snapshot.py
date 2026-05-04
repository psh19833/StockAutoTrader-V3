"""Dashboard Snapshot — summary 빌더"""
from __future__ import annotations
from typing import Any

from dashboard.dashboard_models import (
    SystemStatusView, SessionStatusView, MarketRegimeView,
    ScannerCandidateView, RiskDecisionView, DashboardSummary,
)


def build_dashboard_summary(
    live_trading_enabled: bool,
    emergency_stop: bool,
    session_state: str,
    market_regime: str,
    allow_new_buy: bool,
    scanner_candidates: list[ScannerCandidateView],
    quant_scores: list,
    strategy_signals: list,
    risk_decisions: list[RiskDecisionView],
    orders: list,
    fills: list,
) -> DashboardSummary:
    return DashboardSummary(
        system=SystemStatusView(
            live_trading_enabled=live_trading_enabled,
            emergency_stop=emergency_stop,
            modules_loaded=True,
            total_tests=769,
        ),
        session=SessionStatusView(
            session_state=session_state,
            buy_allowed=(session_state == "REGULAR_MARKET"),
            is_trading_day=True,
        ),
        market_regime=MarketRegimeView(
            regime=market_regime,
            allow_new_buy=allow_new_buy,
            total_score=75.5,
            candidate_score_adjustment=5.0,
        ),
        scanner_summary={
            "total": len(scanner_candidates),
            "included": sum(1 for c in scanner_candidates if c.included),
            "excluded": sum(1 for c in scanner_candidates if not c.included),
        },
        quant_summary={"total": len(quant_scores)},
        risk_summary={
            "total": len(risk_decisions),
            "approved": sum(1 for r in risk_decisions if r.allowed),
            "rejected": sum(1 for r in risk_decisions if not r.allowed),
        },
        order_summary={"total": len(orders)},
        fill_summary={"total": len(fills)},
        candidates=scanner_candidates,
        risk_decisions=risk_decisions,
    )
