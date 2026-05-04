"""Reports package — EOD Daily Performance Report"""
from reports.eod_report_models import (
    AccountSummary, TradingSummary, TradeRecord, WinLossMetrics,
    StrategyPerformance, RegimePerformance, ScoreBucket,
    ScannerPerformance, RiskRejectionSummary, SystemHealth,
    EodReport,
)
from reports.daily_performance import (
    compute_win_rate, compute_profit_factor, compute_average_return,
    compute_win_loss_metrics,
)
from reports.eod_report_builder import build_eod_report
from reports.eod_report_formatter import format_eod_report_text
from reports.eod_report_audit import build_eod_report_audit_event
