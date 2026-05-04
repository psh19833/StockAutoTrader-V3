"""EOD Report Formatter — text output for daily report"""
from __future__ import annotations

from reports.eod_report_models import EodReport


def format_eod_report_text(report: EodReport) -> str:
    lines = [
        f"=== SAT3 EOD Report: {report.trading_date} ===",
        "",
        f"Account: PnL {report.account.total_pnl:,}won "
        f"(realized {report.account.total_realized_pnl:,}, "
        f"unrealized {report.account.total_unrealized_pnl:,})",
        f"Return: {report.account.total_return_rate:.2%} "
        f"(net {report.account.net_return_rate:.2%})",
        "",
        f"Trading: {report.trading_summary.total_orders} orders, "
        f"{report.trading_summary.fills} fills, "
        f"{report.trading_summary.cancelled} cancelled, "
        f"{report.trading_summary.failed} failed",
        f"{report.trading_summary.traded_symbols} symbols, "
        f"{report.trading_summary.new_entries} new, "
        f"{report.trading_summary.closed_positions} closed",
        "",
        f"Win/Loss: {report.win_loss.win_count}W / "
        f"{report.win_loss.loss_count}L / "
        f"{report.win_loss.break_even_count}B, "
        f"rate {report.win_loss.win_rate:.1%}, "
        f"PF {report.win_loss.profit_factor:.2f}",
        f"Total profit {report.win_loss.total_profit:,}, "
        f"loss {report.win_loss.total_loss:,}",
        "",
    ]
    if report.strategy_performances:
        lines.append("--- Strategies ---")
        for sp in report.strategy_performances:
            lines.append(
                f"  {sp.strategy_name}: "
                f"{sp.entry_count} entries, "
                f"win {sp.win_rate:.1%}, "
                f"PnL {sp.total_realized_pnl:,}"
            )
    lines.append("")
    lines.append(f"Risk rejections: {report.risk_rejections.total_rejections}")
    lines.append(f"API calls: {report.system_health.total_api_calls}"
                 f" ({report.system_health.failed_api_calls} failed)")
    return "\n".join(lines)
