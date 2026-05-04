"""EOD Report Models — data structures for all 10 report sections"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AccountSummary:
    start_balance: int
    end_balance: int
    total_evaluated: int
    total_realized_pnl: int
    total_unrealized_pnl: int
    total_pnl: int
    total_return_rate: float
    total_fees: int
    total_tax: int
    net_pnl: int
    net_return_rate: float


@dataclass(frozen=True)
class TradingSummary:
    total_orders: int
    buy_orders: int
    sell_orders: int
    fills: int
    cancelled: int
    failed: int
    pending: int = 0
    traded_symbols: int = 0
    new_entries: int = 0
    closed_positions: int = 0


@dataclass(frozen=True)
class TradeRecord:
    symbol: str
    side: str
    realized_pnl: int
    buy_price: int = 0
    sell_price: int = 0
    strategy: str = ""


@dataclass(frozen=True)
class WinLossMetrics:
    win_count: int
    loss_count: int
    break_even_count: int
    total_profit: int
    total_loss: int
    win_rate: float
    avg_profit_rate: float
    avg_loss_rate: float
    avg_profit_amount: int
    profit_factor: float


@dataclass(frozen=True)
class StrategyPerformance:
    strategy_name: str
    signal_count: int
    approved_count: int
    rejected_count: int
    entry_count: int
    closed_count: int
    win_rate: float
    avg_return_rate: float
    total_realized_pnl: int
    max_profit: int
    max_loss: int
    avg_hold_minutes: int
    profit_factor: float
    total_pnl: int = 0


@dataclass(frozen=True)
class RegimePerformance:
    regime: str
    trade_count: int
    win_rate: float
    avg_return_rate: float
    total_pnl: int
    adjusted_trades: int = 0
    blocked_buys: int = 0


@dataclass(frozen=True)
class ScoreBucket:
    bucket_name: str
    min_score: int
    max_score: int
    candidate_count: int
    signal_count: int
    entry_count: int
    win_rate: float
    avg_return_rate: float
    total_pnl: int
    total_return: int = 0


@dataclass(frozen=True)
class ScannerPerformance:
    scanner_type: str
    scan_runs: int
    collected: int
    candidates: int
    evaluated: int
    signals: int
    orders: int
    fills: int
    profitable: int
    total_pnl: int = 0


@dataclass(frozen=True)
class RiskRejectionSummary:
    total_rejections: int
    by_reason: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SystemHealth:
    total_api_calls: int
    failed_api_calls: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    ws_disconnects: int = 0
    ws_reconnects: int = 0
    exception_count: int = 0
    order_failures: int = 0
    data_gaps: int = 0
    stale_data_count: int = 0


@dataclass(frozen=True)
class EodReport:
    trading_date: str
    account: AccountSummary
    trading_summary: TradingSummary
    win_loss: WinLossMetrics
    symbol_performances: list[dict[str, Any]]
    strategy_performances: list[StrategyPerformance]
    regime_performances: list[RegimePerformance]
    score_buckets: list[ScoreBucket]
    scanner_performances: list[ScannerPerformance]
    risk_rejections: RiskRejectionSummary
    system_health: SystemHealth
