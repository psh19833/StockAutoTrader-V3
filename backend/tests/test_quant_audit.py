"""Tests for Quant Audit Event"""
from __future__ import annotations

from datetime import datetime, timezone

from quant.candidate_score import QuantCandidateScore, QuantDecision
from quant.quant_audit import build_quant_audit_event


def _make_score(
    decision: QuantDecision = QuantDecision.PASS,
    scan_run_id: str = "scan_001",
    data_quality_warnings: tuple[str, ...] = (),
) -> QuantCandidateScore:
    return QuantCandidateScore(
        symbol="005930",
        scanner_type="RAPID_SURGE",
        scan_run_id=scan_run_id,
        evaluation_id="eval_abc123",
        liquidity_score=8.0,
        spread_score=7.0,
        volume_score=6.0,
        momentum_score=9.0,
        trend_score=8.5,
        orderbook_score=5.0,
        volatility_safety_score=7.0,
        market_regime_adjustment=5.0,
        symbol_risk_penalty=2.0,
        final_score=53.5,
        decision=decision,
        reasons=("strong_momentum", "high_liquidity"),
        surge_velocity_score=8.0,
        volume_burst_score=7.0,
        intraday_high_proximity_score=9.0,
        vi_proximity_penalty=0.0,
        pullback_failure_penalty=0.0,
        source_endpoints=("kis/quote",),
        data_quality_warnings=data_quality_warnings,
    )


class TestBuildQuantAuditEvent:
    """QUANT_EVALUATED AuditEvent 변환"""

    def test_event_type(self):
        score = _make_score()
        event = build_quant_audit_event(score)
        assert event.event_type == "QUANT_EVALUATED"

    def test_scan_run_id_linked(self):
        score = _make_score(scan_run_id="scan_999")
        event = build_quant_audit_event(score)
        assert event.scan_run_id == "scan_999"

    def test_correlation_id_linked(self):
        score = _make_score()
        event = build_quant_audit_event(score)
        assert event.correlation_id == "eval_abc123"

    def test_payload_includes_final_score(self):
        event = build_quant_audit_event(_make_score())
        assert "final_score" in str(event.payload)

    def test_payload_includes_decision(self):
        event = build_quant_audit_event(_make_score())
        assert "decision" in event.payload
        assert event.payload["decision"] == "PASS"

    def test_payload_includes_reasons(self):
        event = build_quant_audit_event(_make_score())
        assert "reasons" in event.payload
        assert "strong_momentum" in event.payload["reasons"]

    def test_payload_includes_scanner_type(self):
        event = build_quant_audit_event(_make_score())
        assert "scanner_type" in event.payload
        assert event.payload["scanner_type"] == "RAPID_SURGE"

    def test_payload_includes_symbol(self):
        event = build_quant_audit_event(_make_score())
        assert "symbol" in event.payload
        assert event.payload["symbol"] == "005930"

    def test_payload_includes_detailed_scores(self):
        event = build_quant_audit_event(_make_score())
        payload = event.payload
        assert payload["liquidity_score"] == 8.0
        assert payload["momentum_score"] == 9.0
        assert payload["trend_score"] == 8.5

    def test_payload_includes_regime_adjustment(self):
        event = build_quant_audit_event(_make_score())
        assert event.payload["market_regime_adjustment"] == 5.0

    def test_payload_includes_rapid_surge_scores(self):
        event = build_quant_audit_event(_make_score())
        assert event.payload["surge_velocity_score"] == 8.0
        assert event.payload["volume_burst_score"] == 7.0

    def test_watch_decision_in_payload(self):
        score = _make_score(decision=QuantDecision.WATCH)
        event = build_quant_audit_event(score)
        assert event.payload["decision"] == "WATCH"

    def test_reject_decision_in_payload(self):
        score = _make_score(decision=QuantDecision.REJECT)
        event = build_quant_audit_event(score)
        assert event.payload["decision"] == "REJECT"

    def test_source_endpoints_in_payload(self):
        event = build_quant_audit_event(_make_score())
        assert "source_endpoints" in event.payload
        assert "kis/quote" in event.payload["source_endpoints"]

    def test_data_quality_warnings_in_payload(self):
        score = _make_score(
            data_quality_warnings=("low_volume_data",)
        )
        event = build_quant_audit_event(score)
        assert "data_quality_warnings" in event.payload
        assert "low_volume_data" in event.payload["data_quality_warnings"]

    def test_timestamp_is_recent(self):
        event = build_quant_audit_event(_make_score())
        now = datetime.now(timezone.utc)
        diff = now - event.timestamp
        assert diff.seconds < 10

    def test_no_order_fields_in_event(self):
        event = build_quant_audit_event(_make_score())
        payload_str = str(event.payload)
        for field in ["buy_signal", "sell_signal", "order_intent",
                       "quantity", "stop_loss", "take_profit"]:
            assert field not in payload_str