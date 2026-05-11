from __future__ import annotations

from runtime.orchestrator import Orchestrator
from runtime.scheduler import SessionState


def test_orchestrator_default_is_dry_run_and_marks_mode():
    orch = Orchestrator()
    result = orch.tick(SessionState.REGULAR_MARKET)
    assert result.get("mode") == "dry-run"
    # if SCAN is in plan, it should never claim live
    assert "live" not in result


def test_orchestrator_live_mode_does_not_use_dry_runner_and_is_blocked_not_configured():
    orch = Orchestrator()
    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")
    assert result.get("mode") == "live"
    assert "dry_run" not in result  # must not run DryDecisionRunner in live mode
    live = result.get("live")
    assert isinstance(live, dict)
    assert live.get("status") in (
        "BLOCKED_NOT_CONFIGURED",
        "BLOCKED_NOT_IMPLEMENTED",
        "BLOCKED_NOT_ENABLED",
        "BLOCKED_PRECONDITION_FAILED",
    )


def test_orchestrator_live_mode_blocks_when_runner_enabled_but_readiness_false(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    orch = Orchestrator(live_readiness_provider=lambda: (False, ["SESSION_REGULAR_MARKET"]))
    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")

    live = result.get("live") or {}
    assert live.get("status") == "BLOCKED_PRECONDITION_FAILED"
    assert live.get("ready") is False
    assert "SESSION_REGULAR_MARKET" in (live.get("block_reasons") or [])


def test_orchestrator_live_mode_exposes_live_zero_counts_and_synthetic_audit_when_ready(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    orch = Orchestrator(live_readiness_provider=lambda: (True, []))

    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")

    live = result.get("live") or {}
    assert live.get("status") == "LIVE_PIPELINE_TICK_EXECUTED"
    pipeline = live.get("pipeline") or {}
    assert int(pipeline.get("scanner_candidates_count", 0)) == 0
    assert int(pipeline.get("strategy_signals_count", 0)) == 0
    assert int(pipeline.get("risk_approved_count", 0)) == 0
    assert int(pipeline.get("order_intents_count", 0)) == 0
    assert int(pipeline.get("synthetic_candidates_count", 0)) >= 1
    assert int(pipeline.get("synthetic_order_intents_count", 0)) >= 1
    assert pipeline.get("live_pipeline_reason") == "LIVE_SCANNER_NOT_CONNECTED"
    assert pipeline.get("order_submit_enabled") is False
    assert pipeline.get("actual_order_submitted") is False
