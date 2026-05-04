"""Performance Analytics (N18).

Win rate, return, PnL, profit factor, drawdown, strategy/regime grouping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PerformanceMetrics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_hold_seconds: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def profit_factor(self) -> float:
        return self.gross_profit / abs(self.gross_loss) if self.gross_loss != 0 else 0.0

    @property
    def net_pnl(self) -> float:
        return self.gross_profit + self.gross_loss


class PerformanceAnalyzer:
    """Analyze trading performance."""

    def __init__(self):
        self._trades: list[dict] = []
        self._daily: dict[str, PerformanceMetrics] = {}
        self._by_strategy: dict[str, PerformanceMetrics] = {}
        self._by_regime: dict[str, PerformanceMetrics] = {}

    def add_trade(self, trade: dict) -> None:
        self._trades.append(trade)

    def analyze(self) -> PerformanceMetrics:
        metrics = PerformanceMetrics()
        metrics.total_trades = len(self._trades)
        for t in self._trades:
            pnl = t.get("pnl", 0)
            if pnl > 0:
                metrics.wins += 1
                metrics.gross_profit += pnl
            else:
                metrics.losses += 1
                metrics.gross_loss += pnl
        return metrics

    def by_strategy(self, strategy: str) -> PerformanceMetrics:
        return self._by_strategy.get(strategy, PerformanceMetrics())

    def by_regime(self, regime: str) -> PerformanceMetrics:
        return self._by_regime.get(regime, PerformanceMetrics())
