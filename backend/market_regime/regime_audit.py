"""MarketRegimeAudit — MarketRegimeResult → AuditEvent 변환

secret masking은 audit_logging.log_sanitizer 구조를 따른다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from audit_logging.audit_event import AuditEvent, AuditEventType
from market_regime.regime_result import MarketRegimeResult


def regime_result_to_audit_event(
    result: MarketRegimeResult,
    correlation_id: str | None = None,
    source: str = "market_regime",
) -> AuditEvent:
    """MarketRegimeResult → MARKET_REGIME_EVALUATED AuditEvent

    Args:
        result: Market Regime 평가 결과
        correlation_id: 연결할 correlation_id
        source: 이벤트 발생 출처

    Returns:
        MARKET_REGIME_EVALUATED AuditEvent
    """
    payload = {
        "regime": result.regime.value,
        "total_score": round(result.total_score, 2),
        "index_trend_score": round(result.score.index_trend_score, 2),
        "market_breadth_score": round(result.score.market_breadth_score, 2),
        "market_momentum_score": round(result.score.market_momentum_score, 2),
        "volatility_risk_score": round(result.score.volatility_risk_score, 2),
        "trading_value_score": round(result.score.trading_value_score, 2),
        "sector_strength_score": round(result.score.sector_strength_score, 2),
        "foreign_institution_flow_score": round(
            result.score.foreign_institution_flow_score, 2
        ),
        "market_risk_penalty": round(result.score.market_risk_penalty, 2),
        "candidate_score_adjustment": round(result.candidate_score_adjustment, 2),
        "allow_new_buy": result.allow_new_buy,
        "min_candidate_score_required": round(result.min_candidate_score_required, 2),
        "reasons": list(result.reasons),
        "data_quality_warnings": list(result.data_quality_warnings),
        "source_endpoints": list(result.source_endpoints),
    }

    return AuditEvent(
        event_type=AuditEventType.MARKET_REGIME_EVALUATED.value,
        event_time=result.evaluated_at,
        severity="INFO",
        correlation_id=correlation_id,
        payload=payload,
        source=source,
    )