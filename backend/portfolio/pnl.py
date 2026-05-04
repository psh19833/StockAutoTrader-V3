"""PnL — 손익 계산 (실현손익/평가손익 분리)"""
from __future__ import annotations


def compute_realized_pnl(buy_price: int, sell_price: int, quantity: int) -> int:
    """실현손익 계산 — 실제 체결 기준"""
    return (sell_price - buy_price) * quantity


def compute_unrealized_pnl(avg_buy_price: int, current_price: int,
                           quantity: int) -> int:
    """평가손익 계산 — 현재가 기준 (미실현)"""
    return (current_price - avg_buy_price) * quantity
