"""Daily Performance — EOD 계산 함수들"""
from __future__ import annotations

from reports.eod_report_models import TradeRecord, WinLossMetrics


def compute_win_rate(wins: int, losses: int) -> float:
    total = wins + losses
    if total == 0:
        return 0.0
    return wins / total


def compute_profit_factor(total_profit: int, total_loss: int) -> float:
    if total_loss == 0:
        return float('inf') if total_profit > 0 else 0.0
    return total_profit / total_loss


def compute_average_return(total_return: float, count: int) -> float:
    if count == 0:
        return 0.0
    return total_return / count


def compute_win_loss_metrics(trades: list[TradeRecord]) -> WinLossMetrics:
    wins = [t for t in trades if t.realized_pnl > 0]
    losses = [t for t in trades if t.realized_pnl < 0]
    breakevens = [t for t in trades if t.realized_pnl == 0]

    total_profit = sum(t.realized_pnl for t in wins)
    total_loss = abs(sum(t.realized_pnl for t in losses))

    return WinLossMetrics(
        win_count=len(wins),
        loss_count=len(losses),
        break_even_count=len(breakevens),
        total_profit=total_profit,
        total_loss=total_loss,
        win_rate=compute_win_rate(len(wins), len(losses)),
        avg_profit_rate=compute_average_return(
            sum(t.realized_pnl / max(abs(t.buy_price), 1)
                for t in wins if t.buy_price > 0),
            len(wins),
        ) if wins else 0.0,
        avg_loss_rate=compute_average_return(
            sum(abs(t.realized_pnl) / max(abs(t.buy_price), 1)
                for t in losses if t.buy_price > 0),
            len(losses),
        ) if losses else 0.0,
        avg_profit_amount=(total_profit // len(wins)) if wins else 0,
        profit_factor=compute_profit_factor(total_profit, total_loss),
    )
