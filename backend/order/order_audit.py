"""Order Audit — ORDER_INTENT_APPROVED 이벤트 변환"""
from __future__ import annotations
from audit_logging.audit_event import AuditEvent
from order.order_intent import OrderIntent


def build_order_intent_event(intent: OrderIntent) -> AuditEvent:
    return AuditEvent(
        event_type="ORDER_INTENT_APPROVED",
        severity="INFO",
        symbol=intent.symbol,
        source="order",
        payload={
            "order_intent_id": intent.order_intent_id,
            "risk_decision_id": intent.risk_decision_id,
            "signal_id": intent.signal_id,
            "correlation_id": intent.correlation_id,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "order_type": intent.order_type.value,
            "quantity": intent.quantity,
            "estimated_amount": intent.estimated_amount,
            "source_strategy": intent.source_strategy,
            "live_trading_enabled_snapshot": intent.live_trading_enabled_snapshot,
            "approved_by_risk": intent.approved_by_risk,
        },
    )
