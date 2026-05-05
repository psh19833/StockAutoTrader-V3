"""PortfolioSync — 포트폴리오 동기화

KIS 잔고조회 결과 기반 구조만 허용. 가짜 잔고 금지.
Portfolio의 source-of-truth는 KIS REST 잔고/체결 스냅샷이다.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from portfolio.position import PositionSnapshot


@dataclass
class PortfolioSync:
    positions: tuple[PositionSnapshot, ...] = ()
    total_realized_pnl: int = 0
    total_unrealized_pnl: int = 0
    source_of_truth: str = "KIS_REST"
    snapshot_at: datetime | None = None
    stale: bool = True
    mismatch_reasons: tuple[str, ...] = ()

    def add_position(self, pos: PositionSnapshot) -> None:
        self.positions = self.positions + (pos,)

    def update_snapshot(
        self,
        positions: tuple[PositionSnapshot, ...],
        total_realized_pnl: int,
        total_unrealized_pnl: int,
        source_of_truth: str = "KIS_REST",
        stale: bool = False,
    ) -> None:
        # source-of-truth 강제: KIS REST 외 소스는 mismatch 처리
        if source_of_truth != "KIS_REST":
            self.mismatch_reasons = self.mismatch_reasons + ("invalid_source_of_truth",)
            self.stale = True
            return

        self.positions = positions
        self.total_realized_pnl = total_realized_pnl
        self.total_unrealized_pnl = total_unrealized_pnl
        self.source_of_truth = source_of_truth
        self.snapshot_at = datetime.now(timezone.utc)
        self.stale = stale

    def mark_stale(self, reason: str) -> None:
        self.stale = True
        self.mismatch_reasons = self.mismatch_reasons + (reason,)

    def reconcile_expected_symbols(self, expected_symbols: set[str]) -> bool:
        actual = {p.symbol for p in self.positions}
        missing = sorted(expected_symbols - actual)
        unexpected = sorted(actual - expected_symbols)
        if missing:
            self.mismatch_reasons = self.mismatch_reasons + (f"missing:{','.join(missing)}",)
        if unexpected:
            self.mismatch_reasons = self.mismatch_reasons + (f"unexpected:{','.join(unexpected)}",)
        return not missing and not unexpected
