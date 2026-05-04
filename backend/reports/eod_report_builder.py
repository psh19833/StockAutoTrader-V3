"""EOD Report Builder — aggregate all sections into EodReport"""
from __future__ import annotations

from reports.eod_report_models import (
    AccountSummary, TradingSummary, WinLossMetrics,
    StrategyPerformance, RegimePerformance, ScoreBucket,
    ScannerPerformance, RiskRejectionSummary, SystemHealth,
    EodReport,
)


def build_eod_report(
    trading_date: str,
    account: AccountSummary,
    trading_summary: TradingSummary,
    win_loss: WinLossMetrics,
    symbol_performances: list,
    strategy_performances: list[StrategyPerformance],
    regime_performances: list[RegimePerformance],
    score_buckets: list[ScoreBucket],
    scanner_performances: list[ScannerPerformance],
    risk_rejections: RiskRejectionSummary,
    system_health: SystemHealth,
) -> EodReport:
    return EodReport(
        trading_date=trading_date,
        account=account,
        trading_summary=trading_summary,
        win_loss=win_loss,
        symbol_performances=symbol_performances,
        strategy_performances=strategy_performances,
        regime_performances=regime_performances,
        score_buckets=score_buckets,
        scanner_performances=scanner_performances,
        risk_rejections=risk_rejections,
        system_health=system_health,
    )
