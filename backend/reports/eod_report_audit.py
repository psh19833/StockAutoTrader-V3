"""EOD Report Audit — EOD_REPORT_CREATED"""
from __future__ import annotations
from audit_logging.audit_event import AuditEvent
from reports.eod_report_models import EodReport


def build_eod_report_audit_event(report: EodReport) -> AuditEvent:
    return AuditEvent(
        event_type="EOD_REPORT_CREATED",
        severity="INFO",
        source="reports",
        payload={
            "trading_date": report.trading_date,
            "total_pnl": report.account.total_pnl,
            "total_realized_pnl": report.account.total_realized_pnl,
            "total_unrealized_pnl": report.account.total_unrealized_pnl,
            "total_orders": report.trading_summary.total_orders,
            "fills": report.trading_summary.fills,
            "win_rate": report.win_loss.win_rate,
            "profit_factor": report.win_loss.profit_factor,
            "risk_rejections": report.risk_rejections.total_rejections,
            "api_calls": report.system_health.total_api_calls,
        },
    )
