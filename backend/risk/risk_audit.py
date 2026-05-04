"""Risk Audit — RISK_APPROVED / RISK_REJECTED 이벤트 변환"""
from __future__ import annotations

from audit_logging.audit_event import AuditEvent
from risk.risk_decision import RiskDecision


def build_risk_audit_event(decision: RiskDecision) -> AuditEvent:
    """RiskDecision → RISK_APPROVED / RISK_REJECTED AuditEvent"""
    event_type = "RISK_APPROVED" if decision.allowed else "RISK_REJECTED"
    return AuditEvent(
        event_type=event_type,
        severity="INFO" if decision.allowed else "WARN",
        symbol=decision.symbol,
        source="risk",
        payload={
            "risk_decision_id": decision.risk_decision_id,
            "signal_id": decision.signal_id,
            "correlation_id": decision.correlation_id,
            "symbol": decision.symbol,
            "side": decision.side,
            "allowed": decision.allowed,
            "reason_code": decision.reason_code,
            "reason_text": decision.reason_text,
            "checked_items": list(decision.checked_items),
            "failed_items": list(decision.failed_items),
            "market_regime": decision.market_regime,
            "session_state": decision.session_state,
        },
    )
