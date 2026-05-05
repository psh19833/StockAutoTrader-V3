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
    assert live.get("status") in ("BLOCKED_NOT_CONFIGURED", "BLOCKED_NOT_IMPLEMENTED")
