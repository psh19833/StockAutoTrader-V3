from __future__ import annotations

from scanner.candidate import ScannerCandidate
from scanner.scanner_types import ScannerType
from quant.candidate_score import QuantCandidateScore, QuantDecision
from risk.risk_decision import RiskDecision
from risk.risk_types import RiskDecisionStatus
from safety.live_order_safety_gate import LiveOrderSafetyGate

from evidence.checklist_mappers import (
    scanner_candidate_to_checklist,
    quant_score_to_checklist,
    risk_decision_to_checklist,
    safety_gate_result_to_checklist,
)


def test_scanner_candidate_mapper_has_required_fields():
    c = ScannerCandidate(
        symbol="005930",
        market="KOSPI",
        product_type="COMMON_STOCK",
        scanner_type=ScannerType.RAPID_SURGE,
        scan_run_id="scan_001",
        included=False,
        excluded_reason="ETF_EXCLUDED",
    )
    r = scanner_candidate_to_checklist(c).to_dict()
    assert r["schema_version"]
    assert r["stage"] == "SCANNER"
    assert r["scanner_type"] == "RAPID_SURGE"
    assert isinstance(r["items"], list)
    # Ensure required item fields exist
    item = r["items"][0]
    for f in ["key", "label", "status", "value", "threshold", "reason", "source", "evaluated_at"]:
        assert f in item


def test_quant_mapper_status_mapping():
    s = QuantCandidateScore(
        symbol="005930",
        scanner_type="RAPID_SURGE",
        scan_run_id="scan_001",
        evaluation_id="q_001",
        final_score=88.0,
        decision=QuantDecision.PASS,
        reasons=("ok",),
    )
    r = quant_score_to_checklist(s).to_dict()
    assert r["stage"] == "QUANT"
    assert r["scanner_type"] == "RAPID_SURGE"
    assert r["items"][0]["status"] == "PASS"


def test_risk_mapper_basic():
    d = RiskDecision(
        risk_decision_id="rd_1",
        signal_id="sig_1",
        correlation_id="corr_1",
        symbol="005930",
        side="BUY",
        status=RiskDecisionStatus.APPROVED,
        allowed=True,
        reason_code="APPROVED",
        reason_text="",
    )
    r = risk_decision_to_checklist(d).to_dict()
    assert r["stage"] == "RISK"
    assert r["correlation_id"] == "corr_1"
    assert r["items"][0]["status"] == "PASS"


def test_safety_gate_mapper():
    gate = LiveOrderSafetyGate()
    res = gate.check(
        live_trading_enabled=False,
        session="REGULAR_MARKET",
        market_regime="BULL",
        risk_approved=True,
    )
    r = safety_gate_result_to_checklist(res, correlation_id="corr").to_dict()
    assert r["stage"] == "SAFETY_GATE"
    assert r["items"][0]["key"] == "safety.passed"
    # live_trading_enabled False -> should FAIL overall
    assert r["items"][0]["status"] == "FAIL"
