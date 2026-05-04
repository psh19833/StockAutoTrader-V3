"""Portfolio Audit — 포트폴리오 이벤트 변환"""
from __future__ import annotations
from audit_logging.audit_event import AuditEvent


def build_portfolio_audit_event(event_type: str, total_realized: int,
                                total_unrealized: int,
                                position_count: int) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        severity="INFO",
        source="portfolio",
        payload={
            "total_realized_pnl": total_realized,
            "total_unrealized_pnl": total_unrealized,
            "position_count": position_count,
        },
    )
