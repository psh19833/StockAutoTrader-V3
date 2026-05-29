from __future__ import annotations

from runtime.orchestrator import Orchestrator
from runtime.scheduler import SessionState


def _fake_live_real_audit(
    *,
    symbol: str = "018880",
    candidates_count: int = 1,
    signals_count: int = 1,
    risk_count: int = 1,
    order_intents_count: int = 1,
    selected_product_type: str = "COMMON_STOCK",
) -> dict[str, object]:
    candidates = []
    for idx in range(candidates_count):
        sym = symbol if idx == 0 else f"{symbol}{idx}"
        candidates.append(
            {
                "symbol": sym,
                "scanner_type": "RAPID_SURGE",
                "included": True,
                "generated_at": "2026-01-01T00:00:00+00:00",
                "source": "LIVE_SCANNER",
                "mode": "LIVE",
                "synthetic": False,
                "origin": "live",
                "scan_id": "scan_live_1",
                "run_id": "candidate:scan_live_1",
                "is_live_candidate": True,
                "product_type": selected_product_type,
                "metrics": {"product_type": selected_product_type, "current_price": 1000, "trading_value": 1000000},
            }
        )
    selected = candidates[0] if candidates else None
    signals = []
    risk_decisions = []
    order_intents = []
    if selected is not None and signals_count:
        signals = [
            {
                "signal_id": "sig_1",
                "correlation_id": "corr_1",
                "symbol": selected["symbol"],
                "side": "BUY",
                "strategy_type": "RAPID_SURGE",
                "confidence": 0.81,
                "market_regime": "BULL",
                "scanner_type": "RAPID_SURGE",
                "source_endpoints": [],
                "mode": "LIVE",
                "synthetic": False,
                "source": "LIVE_REAL_READONLY_AUDIT",
            }
        ]
    if selected is not None and risk_count:
        risk_decisions = [
            {
                "risk_decision_id": "risk_1",
                "signal_id": "sig_1",
                "correlation_id": "corr_1",
                "symbol": selected["symbol"],
                "side": "BUY",
                "allowed": True,
                "reason_code": "RISK_OK",
                "reason_text": "OK",
                "mode": "LIVE",
                "synthetic": False,
                "source": "LIVE_REAL_READONLY_AUDIT",
            }
        ]
    if selected is not None and order_intents_count:
        order_intents = [
            {
                "order_intent_id": "oi_1",
                "risk_decision_id": "risk_1",
                "signal_id": "sig_1",
                "correlation_id": "corr_1",
                "symbol": selected["symbol"],
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 1,
                "price": 1000,
                "estimated_amount": 1000,
                "source_strategy": "RAPID_SURGE",
                "source_endpoints": [],
                "live_trading_enabled_snapshot": False,
                "approved_by_risk": True,
                "submitted": False,
                "blocked_reason": "AUDIT_ONLY_NO_SUBMIT",
                "mode": "LIVE",
                "synthetic": False,
                "source": "LIVE_REAL_READONLY_AUDIT",
            }
        ]
    return {
        "source": "LIVE_REAL_READONLY_AUDIT",
        "synthetic": False,
        "mode": "LIVE",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "scan_id": "scan_live_1",
        "scanner_status": "READY" if candidates else "BLOCKED",
        "scanner_reason": "LIVE_SCANNER_OK" if candidates else "LIVE_SCANNER_NO_CANDIDATES",
        "universe": {"count": candidates_count},
        "candidates": candidates,
        "scores": ([{"symbol": selected["symbol"], "scanner_type": "RAPID_SURGE", "decision": "PASS", "final_score": 75.0, "liquidity_score": 20.0, "momentum_score": 15.0, "mode": "LIVE", "synthetic": False, "source": "LIVE_REAL_READONLY_AUDIT"}] if selected and signals_count else []),
        "signals": signals,
        "risk_decisions": risk_decisions,
        "order_intents": order_intents,
        "selected_candidate": selected,
        "actual_order_submitted": False,
        "next_blocking_point": None if candidates else "scanner(no_candidates)",
    }


def test_orchestrator_default_is_dry_run_and_marks_mode(monkeypatch):
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: _fake_live_real_audit())
    orch = Orchestrator()
    result = orch.tick(SessionState.REGULAR_MARKET)
    assert result.get("mode") == "dry-run"
    assert "live" not in result
    assert (result.get("live_real_pipeline_data") or {}).get("candidates")


def test_orchestrator_live_mode_does_not_use_dry_runner_and_is_blocked_not_configured(monkeypatch):
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: _fake_live_real_audit())
    orch = Orchestrator()

    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")
    assert result.get("mode") == "live"
    assert "dry_run" not in result  # must not expose DryDecisionRunner output in live mode
    live = result.get("live")
    assert isinstance(live, dict)
    assert live.get("status") in (
        "BLOCKED_NOT_CONFIGURED",
        "BLOCKED_NOT_IMPLEMENTED",
        "BLOCKED_NOT_ENABLED",
        "BLOCKED_PRECONDITION_FAILED",
    )
    pipeline = live.get("pipeline") or {}
    assert int(pipeline.get("scanner_candidates_count", 0)) == 1
    assert int(pipeline.get("strategy_signals_count", 0)) == 1
    assert int(pipeline.get("risk_approved_count", 0)) == 1
    assert int(pipeline.get("order_intents_count", 0)) == 1
    assert (result.get("live_real_pipeline_data") or {}).get("candidates")


def test_orchestrator_live_mode_blocks_when_runner_enabled_but_readiness_false(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: _fake_live_real_audit())
    orch = Orchestrator(live_readiness_provider=lambda: (False, ["SESSION_REGULAR_MARKET"]))
    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")

    live = result.get("live") or {}
    assert live.get("status") == "BLOCKED_PRECONDITION_FAILED"
    assert live.get("ready") is False
    assert "SESSION_REGULAR_MARKET" in (live.get("block_reasons") or [])


def test_orchestrator_live_mode_exposes_live_zero_counts_and_synthetic_audit_when_ready(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: _fake_live_real_audit(candidates_count=0, signals_count=0, risk_count=0, order_intents_count=0))
    orch = Orchestrator(live_readiness_provider=lambda: (True, []))

    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")

    live = result.get("live") or {}
    assert live.get("status") == "LIVE_PIPELINE_TICK_EXECUTED"
    pipeline = live.get("pipeline") or {}
    assert int(pipeline.get("scanner_candidates_count", 0)) == 0
    assert int(pipeline.get("strategy_signals_count", 0)) == 0
    assert int(pipeline.get("risk_approved_count", 0)) == 0
    assert int(pipeline.get("order_intents_count", 0)) == 0
    assert pipeline.get("live_pipeline_reason") in {"LIVE_SCANNER_NO_CANDIDATES", "LIVE_SCANNER_NOT_CONNECTED"}
    assert pipeline.get("order_submit_enabled") is False
    assert pipeline.get("actual_order_submitted") is False
    assert result.get("synthetic_audit") is not None


def test_orchestrator_live_mode_waiting_off_market_has_zero_live_counts(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: _fake_live_real_audit(candidates_count=0, signals_count=0, risk_count=0, order_intents_count=0))
    orch = Orchestrator(live_readiness_provider=lambda: (True, []))

    result = orch.tick(SessionState.CLOSED_AFTER_MARKET, mode="live")
    live = result.get("live") or {}
    assert live.get("status") == "BLOCKED_SESSION"
    pipeline = live.get("pipeline") or {}
    assert pipeline.get("scanner_status") == "WAITING_FOR_REGULAR_MARKET"
    assert pipeline.get("live_pipeline_reason") == "SESSION_NOT_REGULAR_MARKET"
    assert int(pipeline.get("scanner_candidates_count", 0)) == 0
    assert int(pipeline.get("order_intents_count", 0)) == 0
    assert pipeline.get("actual_order_submitted") is False
    assert pipeline.get("order_submit_enabled") is False


def test_orchestrator_live_mode_uses_live_candidates_only_and_keeps_submit_blocked(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: _fake_live_real_audit(symbol="005930", selected_product_type="COMMON_STOCK"))
    orch = Orchestrator(live_readiness_provider=lambda: (True, []))

    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")
    pipeline = ((result.get("live") or {}).get("pipeline") or {})

    assert int(pipeline.get("scanner_candidates_count", 0)) == 1
    assert int(pipeline.get("strategy_signals_count", 0)) == 1
    assert int(pipeline.get("risk_approved_count", 0)) == 1
    assert int(pipeline.get("order_intents_count", 0)) == 1
    assert int(pipeline.get("synthetic_candidates_count", 0)) >= 0
    assert pipeline.get("actual_order_submitted") is False
    assert pipeline.get("order_submit_enabled") is False

    sample = (pipeline.get("scanner_candidates_sample") or [{}])[0]
    assert sample.get("source") == "LIVE_SCANNER"
    assert sample.get("mode") == "LIVE"
    assert sample.get("synthetic") is False
    assert bool(sample.get("scan_id")) is True
