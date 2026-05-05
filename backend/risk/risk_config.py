"""Risk Limits — 설정 가능한 리스크 제한값"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    """Risk Engine 설정 가능 제한값

    기본값은 안전하게 보수적으로 설정.
    실제 운영값은 설정에서 주입 가능하도록 설계.
    """
    max_amount_per_symbol: int = 10_000_000        # 종목당 최대 금액
    max_daily_loss_pct: float = 0.05               # 예수금 대비 일일손실한도 5%
    reentry_block_minutes: int = 30                 # 재진입 제한 시간
    min_candidate_score_for_buy: float = 50.0       # 최소 퀀트 점수
    max_position_count: int = 5                     # 최대 보유 포지션 수
