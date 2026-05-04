"""Exit Strategy Engine (N16).

Stop loss, take profit, trailing stop, time stop, volatility stop.
All exits require SafetyGate approval before order submission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExitSignal:
    symbol: str
    reason: str
    exit_price: int = 0
    urgency: str = "NORMAL"


class ExitEngine:
    """Generates exit signals from position + market data."""

    def __init__(self):
        self._stop_loss_pct: float = -0.03
        self._take_profit_pct: float = 0.05
        self._trailing_stop_pct: float = -0.02

    def check_stop_loss(self, entry_price: int, current_price: int) -> Optional[ExitSignal]:
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct <= self._stop_loss_pct:
            return ExitSignal(symbol="", reason="STOP_LOSS", exit_price=current_price, urgency="HIGH")
        return None

    def check_take_profit(self, entry_price: int, current_price: int) -> Optional[ExitSignal]:
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct >= self._take_profit_pct:
            return ExitSignal(symbol="", reason="TAKE_PROFIT", exit_price=current_price)
        return None

    def evaluate(self, symbol: str, entry_price: int, current_price: int) -> list[ExitSignal]:
        signals = []
        sl = self.check_stop_loss(entry_price, current_price)
        if sl:
            sl.symbol = symbol
            signals.append(sl)
        tp = self.check_take_profit(entry_price, current_price)
        if tp:
            tp.symbol = symbol
            signals.append(tp)
        return signals
