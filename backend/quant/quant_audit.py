"""Quant Audit — QUANT_EVALUATED AuditEvent 변환

QuantCandidateScore → AuditEvent
Quant의 평가 결과를 Audit 시스템으로 전달한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from quant.candidate_score import QuantCandidateScore
from evidence.checklist_mappers import quant_score_to_checklist


def build_quant_audit_event(
    score: QuantCandidateScore,
    event_type: str = "QUANT_EVALUATED",
) -> Any:
    """QuantCandidateScore를 AuditEvent로 변환

    Args:
        score: Quant 평가 결과
        event_type: Audit 이벤트 타입 (기본: QUANT_EVALUATED)

    Returns:
        AuditEvent (AuditEventType.QUANT_EVALUATED)
    """
    return AuditEvent(
        event_type=event_type,
        scan_run_id=score.scan_run_id,
        correlation_id=score.evaluation_id,
        symbol=score.symbol,
        timestamp=datetime.now(timezone.utc),
        payload={
            # 식별 정보
            "symbol": score.symbol,
            "scanner_type": score.scanner_type,
            "decision": score.decision.value,
            "final_score": score.final_score,
            "reasons": list(score.reasons),
            # Evidence checklist (schema + result)
            "checklist": quant_score_to_checklist(score).to_dict(),
            # 공통 점수
            "liquidity_score": score.liquidity_score,
            "spread_score": score.spread_score,
            "volume_score": score.volume_score,
            "momentum_score": score.momentum_score,
            "trend_score": score.trend_score,
            "orderbook_score": score.orderbook_score,
            "volatility_safety_score": score.volatility_safety_score,
            # 보정
            "market_regime_adjustment": score.market_regime_adjustment,
            "symbol_risk_penalty": score.symbol_risk_penalty,
            # Scanner Type별 점수
            "surge_velocity_score": score.surge_velocity_score,
            "volume_burst_score": score.volume_burst_score,
            "intraday_high_proximity_score": score.intraday_high_proximity_score,
            "vi_proximity_penalty": score.vi_proximity_penalty,
            "pullback_failure_penalty": score.pullback_failure_penalty,
            "prior_strength_score": score.prior_strength_score,
            "pullback_depth_score": score.pullback_depth_score,
            "rebound_confirmation_score": score.rebound_confirmation_score,
            "support_holding_score": score.support_holding_score,
            # 출처 및 품질
            "source_endpoints": list(score.source_endpoints),
            "data_quality_warnings": list(score.data_quality_warnings),
        },
    )


# ── Audit Event (local minimal class) ──


class AuditEvent:
    """Minimal audit event — 실제 시스템에서 AuditEngine의 이벤트 클래스로 대체"""

    def __init__(
        self,
        event_type: str,
        scan_run_id: str,
        correlation_id: str,
        symbol: str,
        timestamp: datetime,
        payload: dict[str, Any],
    ) -> None:
        self.event_type = event_type
        self.scan_run_id = scan_run_id
        self.correlation_id = correlation_id
        self.symbol = symbol
        self.timestamp = timestamp
        self.payload = payload