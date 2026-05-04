"""Dashboard View Models — 읽기 전용 조회용 모델

모든 View는 Read-Only. 주문 실행 필드 절대 금지.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SystemStatusView:
    live_trading_enabled: bool
    emergency_stop: bool
    modules_loaded: bool
    total_tests: int


@dataclass(frozen=True)
class SessionStatusView:
    session_state: str
    buy_allowed: bool
    is_trading_day: bool
    next_session: str = ""


@dataclass(frozen=True)
class MarketRegimeView:
    regime: str
    allow_new_buy: bool
    total_score: float
    candidate_score_adjustment: float


@dataclass(frozen=True)
class ScannerCandidateView:
    symbol: str
    scanner_type: str
    included: bool
    excluded_reason: str | None = None
    symbol_name: str = ""


@dataclass(frozen=True)
class QuantScoreView:
    symbol: str
    scanner_type: str
    decision: str
    final_score: float
    liquidity_score: float = 0
    momentum_score: float = 0


@dataclass(frozen=True)
class StrategySignalView:
    signal_id: str
    symbol: str
    side: str
    strategy_type: str
    confidence: float
    market_regime: str


@dataclass(frozen=True)
class RiskDecisionView:
    risk_decision_id: str
    symbol: str
    side: str
    allowed: bool
    reason_code: str
    reason_text: str = ""


@dataclass(frozen=True)
class OrderStatusView:
    order_intent_id: str
    symbol: str
    side: str
    status: str
    allowed: bool


@dataclass(frozen=True)
class FillStatusView:
    fill_id: str
    order_intent_id: str
    symbol: str
    side: str
    filled_qty: int
    filled_price: int
    remaining_qty: int


@dataclass(frozen=True)
class PortfolioView:
    symbol: str
    name: str
    quantity: int
    avg_buy_price: int
    current_price: int
    unrealized_pnl: int = 0


@dataclass(frozen=True)
class EodReportView:
    trading_date: str
    total_pnl: int
    total_realized_pnl: int
    total_unrealized_pnl: int
    win_rate: float
    profit_factor: float
    total_orders: int
    fills: int


@dataclass(frozen=True)
class AuditTimelineView:
    event_type: str
    correlation_id: str
    symbol: str
    timestamp: str
    severity: str = "INFO"


@dataclass(frozen=True)
class DashboardSummary:
    system: SystemStatusView
    session: SessionStatusView
    market_regime: MarketRegimeView
    scanner_summary: dict[str, int]
    quant_summary: dict[str, int]
    risk_summary: dict[str, int]
    order_summary: dict[str, int]
    fill_summary: dict[str, int]
    candidates: list[ScannerCandidateView]
    risk_decisions: list[RiskDecisionView]
