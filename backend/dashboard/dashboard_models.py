"""Dashboard View Models — 읽기 전용 조회용 모델

모든 View는 Read-Only. 주문 실행 필드 절대 금지.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
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
    reason: str = ""
    detail: str = ""


@dataclass(frozen=True)
class MarketRegimeView:
    regime: str
    allow_new_buy: bool
    total_score: float
    candidate_score_adjustment: float
    reason: str = ""
    factors: str = ""


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
    # Minimal fields
    event_type: str
    correlation_id: str
    symbol: str
    timestamp: str  # kept for backward compatibility (event_time)

    # Extended fields for UI (safe defaults)
    event_id: str = ""
    severity: str = "INFO"
    source: str = ""
    strategy_name: str = ""
    status: str = ""
    summary: str = ""
    has_checklist: bool = False


@dataclass(frozen=True)
class WebSocketStatusView:
    """WebSocket 연결 상태 표시 (Read-Only).

    Dashboard에서 WebSocket 상태를 조회하기 위한 View Model.
    주문 버튼/주문 실행 필드는 절대 포함하지 않음.
    """

    connection_state: str = "DISCONNECTED"
    subscribed_channels: list[str] = field(default_factory=list)
    last_message_at: datetime | None = None
    reconnect_count: int = 0
    last_error_type: str | None = None
    data_quality_warnings: list[str] = field(default_factory=list)
    source: str = "KIS_API_WS"

    @classmethod
    def from_status(cls, status: Any) -> "WebSocketStatusView":
        """Convert WebSocketConnectionStatus to a Dashboard view."""
        return cls(
            connection_state=status.connection_state,
            subscribed_channels=list(status.subscribed_channels),
            last_message_at=status.last_message_at,
            reconnect_count=status.reconnect_count,
            last_error_type=status.last_error_type,
            data_quality_warnings=list(status.data_quality_warnings),
            source=status.source,
        )


@dataclass(frozen=True)
class DataRouterStatusView:
    """REST + WebSocket data router 상태 표시 (Read-Only)."""
    ws_connected: bool = False
    rest_available: bool = True
    stale_warnings: list[str] = field(default_factory=list)
    source: str = "KIS_API_REST"


@dataclass(frozen=True)
class TelegramStatusView:
    """Telegram 봇 연결 상태 (로컬 대시보드 — chat_id 전체 표시)."""
    connected: bool = False
    bot_name: str = ""
    chat_id: str = ""
    last_message_at: str = ""
    error: str = ""


@dataclass(frozen=True)
class KisAccountView:
    """KIS 계좌 정보 (로컬 대시보드 — 계좌번호 전체 표시)."""
    account_no: str = ""
    product_code: str = "01"
    deposit: int = 0
    total_value: int = 0
    total_buy_amount: int = 0
    holding_count: int = 0
    d2_deposit: int = 0
    stale: bool = True


@dataclass(frozen=True)
class DailySummaryView:
    """일별 매매 요약."""
    date: str = ""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    realized_pnl: int = 0
    unrealized_pnl: int = 0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_hold_minutes: float = 0.0
    total_commission: int = 0


@dataclass(frozen=True)
class StrategyBreakdownView:
    """전략별 성과 breakdown."""
    strategy: str = ""
    trades: int = 0
    win_rate: float = 0.0
    total_pnl: int = 0
    avg_pnl: float = 0.0


@dataclass(frozen=True)
class LogEntryView:
    """로그 항목 (날짜/카테고리별)."""
    date: str = ""
    category: str = ""
    lines: list[str] = field(default_factory=list)
    available_dates: list[str] = field(default_factory=list)
    available_categories: list[str] = field(default_factory=list)


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
    data_sources: dict[str, str]
    ws_status: WebSocketStatusView | None = None
    data_router: dict[str, Any] | None = None
