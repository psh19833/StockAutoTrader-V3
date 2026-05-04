"""PortfolioSync — 포트폴리오 동기화

KIS 잔고조회 결과 기반 구조만 허용. 가짜 잔고 금지.
Phase 7에서는 실제 HTTP 호출 금지.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from portfolio.position import PositionSnapshot


@dataclass
class PortfolioSync:
    positions: tuple[PositionSnapshot, ...] = ()
    total_realized_pnl: int = 0
    total_unrealized_pnl: int = 0

    def add_position(self, pos: PositionSnapshot) -> None:
        self.positions = self.positions + (pos,)

    def update_snapshot(self, positions: tuple[PositionSnapshot, ...],
                        total_realized_pnl: int, total_unrealized_pnl: int) -> None:
        self.positions = positions
        self.total_realized_pnl = total_realized_pnl
        self.total_unrealized_pnl = total_unrealized_pnl
