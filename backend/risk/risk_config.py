"""Risk Limits — 설정 가능한 리스크 제한값"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    """Risk Engine 설정 가능 제한값

    기본값은 안전하게 보수적으로 설정.
    실제 운영값은 설정에서 주입 가능하도록 설계.
    """
    max_position_count: int = 5
    max_amount_per_symbol: int = 10_000_000
    max_daily_loss_amount: int = 1_000_000
    max_daily_loss_rate: float = 0.03
    reentry_block_minutes: int = 30
    min_candidate_score_for_buy: float = 50.0
