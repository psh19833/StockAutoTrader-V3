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
    monkeypatch.setattr(
        "runtime.orchestrator.maybe_create_kis_rest_provider",
        lambda: (None, {"configured": False, "reason": "test_isolation"}),
    )
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
    assert pipeline.get("live_pipeline_reason") in {"LIVE_SCANNER_NO_FRESH_DATA", "LIVE_SCANNER_NOT_CONNECTED"}
    assert pipeline.get("order_submit_enabled") is False
    assert pipeline.get("actual_order_submitted") is False


def test_orchestrator_live_mode_waiting_off_market_has_zero_live_counts(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
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
    orch = Orchestrator(live_readiness_provider=lambda: (True, []))

    class _FakeLiveScan:
        status = "READY"
        reason = "LIVE_SCANNER_OK"
        candidates = [
            {
                "symbol": "005930",
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
            }
        ]

        def to_dict(self):
            return {
                "status": self.status,
                "reason": self.reason,
                "generated_at": "2026-01-01T00:00:00+00:00",
                "scan_id": "scan_live_1",
                "source": "LIVE_SCANNER",
                "mode": "LIVE",
                "synthetic": False,
                "candidates": list(self.candidates),
                "error": "",
            }

    monkeypatch.setattr(orch._live_scanner, "run_live_scan", lambda session: _FakeLiveScan())
    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")
    pipeline = ((result.get("live") or {}).get("pipeline") or {})

    assert int(pipeline.get("scanner_candidates_count", 0)) == 1
    assert int(pipeline.get("strategy_signals_count", 0)) == 1
    assert int(pipeline.get("risk_approved_count", 0)) == 1
    assert int(pipeline.get("order_intents_count", 0)) == 1
    assert int(pipeline.get("synthetic_candidates_count", 0)) >= 1
    assert pipeline.get("actual_order_submitted") is False
    assert pipeline.get("order_submit_enabled") is False

    sample = (pipeline.get("scanner_candidates_sample") or [{}])[0]
    assert sample.get("source") == "LIVE_SCANNER"
    assert sample.get("mode") == "LIVE"
    assert sample.get("synthetic") is False
    assert bool(sample.get("scan_id")) is True
