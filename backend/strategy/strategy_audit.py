"""Strategy Audit — STRATEGY_SIGNAL_CREATED 이벤트 변환"""
from __future__ import annotations

from audit_logging.audit_event import AuditEvent, AuditEventType
from strategy.signal import StrategySignal


def build_strategy_signal_event(signal: StrategySignal) -> AuditEvent:
    """StrategySignal → STRATEGY_SIGNAL_CREATED AuditEvent"""
    return AuditEvent(
        event_type="STRATEGY_SIGNAL_CREATED",
        severity="INFO",
        symbol=signal.symbol,
        source="strategy",
        payload={
            "signal_id": signal.signal_id,
            "correlation_id": signal.correlation_id,
            "symbol": signal.symbol,
            "side": signal.side,
            "strategy_type": signal.strategy_type.value,
            "confidence": signal.confidence,
            "scanner_type": signal.scanner_type,
            "market_regime": signal.market_regime,
            "evidence": list(signal.evidence),
            "source_endpoints": list(signal.source_endpoints),
        },
    )
