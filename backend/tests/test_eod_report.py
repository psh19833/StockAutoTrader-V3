"""Tests for EOD Daily Performance Report"""
from __future__ import annotations

from reports.eod_report_models import (
    AccountSummary, TradingSummary, WinLossMetrics,
    TradeRecord, StrategyPerformance, RegimePerformance,
    ScoreBucket, ScannerPerformance, RiskRejectionSummary,
    SystemHealth, EodReport,
)
from reports.daily_performance import (
    compute_win_loss_metrics, compute_win_rate,
    compute_profit_factor, compute_average_return,
)
from reports.eod_report_builder import build_eod_report
from reports.eod_report_formatter import format_eod_report_text


class TestAccountSummary:
    def test_create(self):
        a = AccountSummary(
            start_balance=10_000_000, end_balance=10_500_000,
            total_evaluated=10_700_000, total_realized_pnl=500_000,
            total_unrealized_pnl=200_000, total_pnl=700_000,
            total_return_rate=0.07, total_fees=5000, total_tax=1000,
            net_pnl=694_000, net_return_rate=0.0694,
        )
        assert a.total_realized_pnl == 500_000
        assert a.total_unrealized_pnl == 200_000
        # realized != unrealized
        assert a.total_realized_pnl != a.total_unrealized_pnl


class TestWinLossMetrics:
    def test_win_rate(self):
        rate = compute_win_rate(wins=6, losses=4)
        assert rate == 0.6

    def test_win_rate_zero_trades(self):
        rate = compute_win_rate(wins=0, losses=0)
        assert rate == 0.0

    def test_profit_factor(self):
        pf = compute_profit_factor(total_profit=300_000, total_loss=100_000)
        assert pf == 3.0

    def test_profit_factor_zero_loss(self):
        pf = compute_profit_factor(total_profit=300_000, total_loss=0)
        assert pf == float('inf')

    def test_average_return(self):
        avg = compute_average_return(total_return=0.30, count=3)
        assert abs(avg - 0.10) < 0.001

    def test_compute_win_loss_metrics(self):
        trades = [
            TradeRecord(symbol="A", side="BUY", realized_pnl=10000),
            TradeRecord(symbol="B", side="BUY", realized_pnl=-5000),
            TradeRecord(symbol="C", side="BUY", realized_pnl=20000),
            TradeRecord(symbol="D", side="BUY", realized_pnl=-3000),
        ]
        wl = compute_win_loss_metrics(trades)
        assert wl.win_count == 2
        assert wl.loss_count == 2
        assert wl.total_profit == 30000
        assert wl.total_loss == 8000
        assert wl.profit_factor == 3.75

    def test_break_even_not_counted_as_win_or_loss(self):
        trades = [
            TradeRecord(symbol="A", side="BUY", realized_pnl=10000),
            TradeRecord(symbol="B", side="BUY", realized_pnl=0),
            TradeRecord(symbol="C", side="BUY", realized_pnl=-5000),
        ]
        wl = compute_win_loss_metrics(trades)
        assert wl.win_count == 1
        assert wl.loss_count == 1
        assert wl.break_even_count == 1


class TestEodReportBuilder:
    def test_build_basic_report(self):
        report = build_eod_report(
            trading_date="2026-05-04",
            account=AccountSummary(
                start_balance=10_000_000, end_balance=10_500_000,
                total_evaluated=10_700_000, total_realized_pnl=500_000,
                total_unrealized_pnl=200_000, total_pnl=700_000,
                total_return_rate=0.07, total_fees=5000, total_tax=1000,
                net_pnl=694_000, net_return_rate=0.0694,
            ),
            trading_summary=TradingSummary(
                total_orders=10, buy_orders=6, sell_orders=4,
                fills=8, cancelled=1, failed=1,
                traded_symbols=3, new_entries=2, closed_positions=1,
            ),
            win_loss=compute_win_loss_metrics([]),
            symbol_performances=[],
            strategy_performances=[],
            regime_performances=[],
            score_buckets=[],
            scanner_performances=[],
            risk_rejections=RiskRejectionSummary(total_rejections=0),
            system_health=SystemHealth(total_api_calls=100),
        )
        assert report.trading_date == "2026-05-04"
        assert report.account.total_realized_pnl == 500_000

    def test_order_success_not_trade_success(self):
        """주문 성공만으로 거래 성과 계산하지 않음 — 체결 기준"""
        report = build_eod_report(
            trading_date="2026-05-04",
            account=AccountSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            trading_summary=TradingSummary(
                total_orders=100, buy_orders=50, sell_orders=50,
                fills=10, cancelled=40, failed=50,
                traded_symbols=3, new_entries=2, closed_positions=1,
            ),
            win_loss=WinLossMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            symbol_performances=[], strategy_performances=[],
            regime_performances=[], score_buckets=[],
            scanner_performances=[],
            risk_rejections=RiskRejectionSummary(0),
            system_health=SystemHealth(0),
        )
        # 100 orders, 10 fills → 성과는 fills 기준
        assert report.trading_summary.fills == 10
        assert report.trading_summary.fills < report.trading_summary.total_orders


class TestEodReportFormatter:
    def test_format_basic(self):
        report = build_eod_report(
            trading_date="2026-05-04",
            account=AccountSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            trading_summary=TradingSummary(0, 0, 0, 0, 0, 0, 0, 0, 0),
            win_loss=WinLossMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            symbol_performances=[], strategy_performances=[],
            regime_performances=[], score_buckets=[],
            scanner_performances=[],
            risk_rejections=RiskRejectionSummary(0),
            system_health=SystemHealth(0),
        )
        text = format_eod_report_text(report)
        assert "2026-05-04" in text
        assert "EOD" in text

    def test_no_secret_in_output(self):
        report = build_eod_report(
            trading_date="2026-05-04",
            account=AccountSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            trading_summary=TradingSummary(0, 0, 0, 0, 0, 0, 0, 0, 0),
            win_loss=WinLossMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            symbol_performances=[], strategy_performances=[],
            regime_performances=[], score_buckets=[],
            scanner_performances=[],
            risk_rejections=RiskRejectionSummary(0),
            system_health=SystemHealth(0),
        )
        text = format_eod_report_text(report)
        for secret in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert secret not in text
