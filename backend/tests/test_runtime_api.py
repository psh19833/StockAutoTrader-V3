from __future__ import annotations

import asyncio
import time

import pytest
import main


class _FakeLiveScan:
    status = "READY"
    reason = "LIVE_SCANNER_OK"
    candidates = [
        {
            "symbol": "018880",
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
            "product_type": "COMMON_STOCK",
            "market": "KOSPI",
            "metrics": {"product_type": "COMMON_STOCK"},
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


def _fake_live_scan(self, session, symbols=None):
    return _FakeLiveScan()


def _fake_live_real_audit(**kwargs):
    candidate = dict(_FakeLiveScan.candidates[0])
    return {
        "source": "LIVE_REAL_READONLY_AUDIT",
        "synthetic": False,
        "mode": "LIVE",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "scan_id": "scan_live_1",
        "scanner_status": "READY",
        "scanner_reason": "LIVE_SCANNER_OK",
        "universe": {"count": 3},
        "candidates": [candidate],
        "scores": [{"symbol": candidate["symbol"], "scanner_type": candidate["scanner_type"], "decision": "PASS", "final_score": 75.0, "liquidity_score": 20.0, "momentum_score": 15.0, "mode": "LIVE", "synthetic": False, "source": "LIVE_REAL_READONLY_AUDIT"}],
        "signals": [{"signal_id": "sig_1", "correlation_id": "corr_1", "symbol": candidate["symbol"], "side": "BUY", "strategy_type": "RAPID_SURGE", "confidence": 0.81, "market_regime": "BULL", "scanner_type": "RAPID_SURGE", "source_endpoints": [], "mode": "LIVE", "synthetic": False, "source": "LIVE_REAL_READONLY_AUDIT"}],
        "risk_decisions": [{"risk_decision_id": "risk_1", "signal_id": "sig_1", "correlation_id": "corr_1", "symbol": candidate["symbol"], "side": "BUY", "allowed": True, "reason_code": "RISK_OK", "reason_text": "OK", "mode": "LIVE", "synthetic": False, "source": "LIVE_REAL_READONLY_AUDIT"}],
        "order_intents": [{"order_intent_id": "oi_1", "risk_decision_id": "risk_1", "signal_id": "sig_1", "correlation_id": "corr_1", "symbol": candidate["symbol"], "side": "BUY", "order_type": "MARKET", "quantity": 1, "price": 1000, "estimated_amount": 1000, "source_strategy": "RAPID_SURGE", "source_endpoints": [], "live_trading_enabled_snapshot": False, "approved_by_risk": True, "submitted": False, "blocked_reason": "AUDIT_ONLY_NO_SUBMIT", "mode": "LIVE", "synthetic": False, "source": "LIVE_REAL_READONLY_AUDIT"}],
        "selected_candidate": candidate,
        "actual_order_submitted": False,
        "next_blocking_point": None,
    }

def _as_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _run(coro):
    return asyncio.run(coro)


def _reset_runtime_state() -> None:
    with main._runtime_lock:
        main._runtime_status["running"] = False
        main._runtime_status["mode"] = "dry-run"
        main._runtime_status["session"] = "REGULAR_MARKET"
        main._runtime_status["interval_sec"] = 10
        main._runtime_status["last_tick_at"] = ""
        main._runtime_status["last_result"] = {}
        main._runtime_status["tick_count"] = 0
        main._runtime_status["live_start_block_reasons"] = []
        main._runtime_status["last_order_status"] = ""


@pytest.fixture(autouse=True)
def _isolate_runtime_state(monkeypatch):
    monkeypatch.setattr("runtime.orchestrator.LiveScannerAdapter.run_live_scan", _fake_live_scan)
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", _fake_live_real_audit)
    _run(main.runtime_stop())
    _reset_runtime_state()
    yield
    _run(main.runtime_stop())
    _reset_runtime_state()


def test_runtime_tick_updates_dashboard_read_models():
    result = _run(main.runtime_tick(mode="dry-run", session="REGULAR_MARKET"))
    assert result.get("mode") == "dry-run"
    dry = result.get("dry_run", {})
    counts = dry.get("counts", {})
    assert counts.get("candidates", 0) >= 1
    assert counts.get("scores", 0) >= 1
    assert counts.get("signals", 0) >= 1
    live_real = result.get("live_real_pipeline_data", {})
    assert len(live_real.get("candidates", []) or []) == 1
    assert len(live_real.get("signals", []) or []) == 1
    assert len(live_real.get("risk_decisions", []) or []) == 1
    assert len(live_real.get("order_intents", []) or []) == 1
    assert live_real.get("actual_order_submitted") is False

    status = _run(main.runtime_status())
    assert _as_int(status.get("tick_count")) >= 1
    assert status.get("order_submit_enabled") in {False, True}

    from dashboard.dashboard_routes import (
        handle_get_candidates,
        handle_get_summary,
        handle_get_strategy_breakdown,
        handle_get_risk_decisions,
    )

    summary = handle_get_summary()
    selected = (summary.get("live_pipeline_summary") or {}).get("selected_candidate", {})
    assert selected.get("symbol") == "018880"
    assert selected.get("product_type") == "COMMON_STOCK"
    assert _as_int((summary.get("live_pipeline_summary") or {}).get("scanner_candidates_count")) == 1
    candidates = handle_get_candidates()
    assert len(candidates) == 1
    assert candidates[0].get("symbol") == "018880"
    assert candidates[0].get("product_type") == "COMMON_STOCK"
    assert len(handle_get_strategy_breakdown()) == 1
    assert len(handle_get_risk_decisions()) == 1


def test_runtime_tick_rejects_live_mode_when_preconditions_fail(monkeypatch):
    forced_checks = {
        "LIVE_TRADING_ENABLED_TRUE": True,
        "CONFIRM_ENV_SET": True,
        "EMERGENCY_STOP_INACTIVE": True,
        "KIS_REST_AVAILABLE": True,
        "KIS_WS_AVAILABLE": True,
        "SESSION_REGULAR_MARKET": False,
        "MARKET_REGIME_KNOWN": True,
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": True,
        "RISK_LIMITS_LOADED": True,
        "TELEGRAM_STATUS_AVAILABLE": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: (forced_checks, {"session": "CLOSED_AFTER_MARKET"}))

    result = _run(main.runtime_tick(mode="live", session="REGULAR_MARKET"))
    assert result.get("mode") == "live"
    assert result.get("status") == "RUNTIME_LIVE_MODE_BLOCKED"
    assert result.get("reason") == "LIVE_START_PRECONDITION_FAILED"
    assert result.get("executed") is False
    assert isinstance(result.get("block_reasons"), list)


def test_runtime_start_rejects_live_mode_when_preconditions_fail(monkeypatch):
    forced_checks = {
        "LIVE_TRADING_ENABLED_TRUE": True,
        "CONFIRM_ENV_SET": True,
        "EMERGENCY_STOP_INACTIVE": True,
        "KIS_REST_AVAILABLE": True,
        "KIS_WS_AVAILABLE": True,
        "SESSION_REGULAR_MARKET": False,
        "MARKET_REGIME_KNOWN": True,
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": True,
        "RISK_LIMITS_LOADED": True,
        "TELEGRAM_STATUS_AVAILABLE": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: (forced_checks, {"session": "CLOSED_AFTER_MARKET"}))

    started = _run(main.runtime_start(mode="live", session="REGULAR_MARKET", interval_sec=1))
    assert started.get("started") is False
    assert started.get("reason") == "LIVE_START_PRECONDITION_FAILED"
    status = started.get("status", {})
    assert status.get("running") is False


def test_runtime_dry_run_still_works():
    result = _run(main.runtime_tick(mode="dry-run", session="REGULAR_MARKET"))
    assert result.get("mode") == "dry-run"
    dry = result.get("dry_run", {})
    assert isinstance(dry.get("counts"), dict)


def test_runtime_start_live_rejects_missing_confirm_account():
    payload = {"confirm": "CONFIRM_LIVE_AUTO_TRADING", "interval_sec": 10}
    result = _run(main.runtime_start_live(payload))
    assert result.get("started") is False
    assert result.get("reason") == "LIVE_CONFIRM_ACCOUNT_REQUIRED"


def test_runtime_start_live_rejects_confirm_account_mismatch(monkeypatch):
    monkeypatch.setenv("KIS_ACCOUNT_NO", "TEST-ACCOUNT-01")
    payload = {
        "confirm": "CONFIRM_LIVE_AUTO_TRADING",
        "confirm_account": "00000000-00",
        "interval_sec": 10,
    }
    result = _run(main.runtime_start_live(payload))
    assert result.get("started") is False
    assert result.get("reason") == "LIVE_CONFIRM_ACCOUNT_MISMATCH"


def test_runtime_start_live_accepts_account_match_but_still_blocks_on_other_blockers(monkeypatch):
    monkeypatch.setenv("KIS_ACCOUNT_NO", "TEST-ACCOUNT-01")

    forced_checks = {
        "LIVE_TRADING_ENABLED_TRUE": True,
        "CONFIRM_ENV_SET": True,
        "EMERGENCY_STOP_INACTIVE": True,
        "KIS_REST_AVAILABLE": True,
        "KIS_WS_AVAILABLE": True,
        "SESSION_REGULAR_MARKET": False,
        "MARKET_REGIME_KNOWN": True,
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": True,
        "RISK_LIMITS_LOADED": True,
        "TELEGRAM_STATUS_AVAILABLE": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: (forced_checks, {"session": "CLOSED_AFTER_MARKET"}))

    payload = {
        "confirm": "CONFIRM_LIVE_AUTO_TRADING",
        "confirm_account": "TEST-ACCOUNT-01",
        "interval_sec": 10,
    }
    result = _run(main.runtime_start_live(payload))
    assert result.get("started") is False
    assert result.get("reason") == "LIVE_START_PRECONDITION_FAILED"
    assert "SESSION_REGULAR_MARKET" in (result.get("block_reasons") or [])


def test_runtime_start_status_stop_cycle():
    started = _run(main.runtime_start(mode="dry-run", session="REGULAR_MARKET", interval_sec=1))
    assert started.get("started") is True or started.get("reason") == "already_running"

    time.sleep(1.2)

    status = _run(main.runtime_status())
    assert isinstance(status, dict)
    assert status.get("mode") == "dry-run"
    assert status.get("session") == "REGULAR_MARKET"
    assert int(status.get("tick_count", 0)) >= 1

    stopped = _run(main.runtime_stop())
    assert stopped.get("stopped") is True


def test_runtime_tick_live_syncs_runtime_state_and_dashboard_when_runner_not_configured(monkeypatch):
    monkeypatch.delenv("SAT3_ENABLE_LIVE_RUNNER", raising=False)
    forced_checks = {
        "LIVE_TRADING_ENABLED_TRUE": True,
        "CONFIRM_ENV_SET": True,
        "EMERGENCY_STOP_INACTIVE": True,
        "KIS_REST_AVAILABLE": True,
        "KIS_REST_FRESH": True,
        "KIS_WS_AVAILABLE": True,
        "KIS_WS_FRESH": True,
        "SESSION_REGULAR_MARKET": True,
        "MARKET_REGIME_KNOWN": True,
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": True,
        "RISK_LIMITS_LOADED": True,
        "TELEGRAM_TARGET_VALID": True,
        "OPEN_ORDER_RECONCILIATION_KNOWN": True,
        "OPEN_ORDER_PENDING": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: (forced_checks, {"session": "REGULAR_MARKET"}))

    import dashboard.dashboard_routes as routes
    import runtime.orchestrator as orchestrator_mod

    monkeypatch.setattr(routes._snapshot_refresher, "maybe_refresh", lambda mode, session: {"enabled": False, "reason": "test_isolation"})

    class _FakeLiveScan:
        status = "READY"
        reason = "LIVE_SCANNER_OK"
        candidates = [
            {
                "symbol": "018880",
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
                "product_type": "COMMON_STOCK",
                "metrics": {"product_type": "COMMON_STOCK"},
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

    monkeypatch.setattr(orchestrator_mod.LiveScannerAdapter, "run_live_scan", lambda self, session, symbols=None: _FakeLiveScan())

    tick = _run(main.runtime_tick(mode="live", session="REGULAR_MARKET"))
    pipeline = ((tick.get("live") or {}).get("pipeline") or {})
    assert tick.get("live_real_pipeline_data", {}).get("candidates")
    assert int(pipeline.get("scanner_candidates_count", 0)) == 1
    assert int(pipeline.get("strategy_signals_count", 0)) == 1
    assert int(pipeline.get("risk_approved_count", 0)) == 1
    assert int(pipeline.get("order_intents_count", 0)) == 1
    assert pipeline.get("actual_order_submitted") is False
    assert pipeline.get("order_submit_enabled") is False

    status = _run(main.runtime_status())
    assert int(status.get("tick_count", 0)) >= 1
    assert isinstance(status.get("last_result"), dict)

    summary = routes.handle_get_summary()
    assert int((summary.get("scanner_summary") or {}).get("total", 0)) == 1
    selected = (summary.get("live_pipeline_summary") or {}).get("selected_candidate", {})
    assert selected.get("symbol") == "018880"
    assert selected.get("product_type") == "COMMON_STOCK"
    candidates = routes.handle_get_candidates()
    assert len(candidates) == 1
    assert candidates[0].get("product_type") == "COMMON_STOCK"
    assert len(routes.handle_get_strategy_breakdown()) == 1
    assert len(routes.handle_get_risk_decisions()) == 1


def test_runtime_tick_live_session_blocked_exposes_waiting_scanner_status(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    monkeypatch.setattr("runtime.orchestrator.build_live_real_readonly_audit", lambda **kwargs: {
        "source": "LIVE_REAL_READONLY_AUDIT",
        "synthetic": False,
        "mode": "LIVE",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "scan_id": "scan_live_1",
        "scanner_status": "WAITING_FOR_REGULAR_MARKET",
        "scanner_reason": "SESSION_NOT_REGULAR_MARKET",
        "universe": {"count": 0},
        "candidates": [],
        "scores": [],
        "signals": [],
        "risk_decisions": [],
        "order_intents": [],
        "selected_candidate": None,
        "actual_order_submitted": False,
        "next_blocking_point": "SESSION_NOT_REGULAR_MARKET",
    })
    forced_checks = {
        "LIVE_TRADING_ENABLED_TRUE": True,
        "CONFIRM_ENV_SET": True,
        "EMERGENCY_STOP_INACTIVE": True,
        "KIS_REST_AVAILABLE": True,
        "KIS_WS_AVAILABLE": True,
        "SESSION_REGULAR_MARKET": True,
        "MARKET_REGIME_KNOWN": True,
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": True,
        "RISK_LIMITS_LOADED": True,
        "TELEGRAM_STATUS_AVAILABLE": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: (forced_checks, {"session": "REGULAR_MARKET"}))

    tick = _run(main.runtime_tick(mode="live", session="CLOSED_AFTER_MARKET"))
    pipeline = ((tick.get("live") or {}).get("pipeline") or {})
    assert pipeline.get("scanner_status") == "WAITING_FOR_REGULAR_MARKET"
    assert pipeline.get("live_pipeline_reason") == "SESSION_NOT_REGULAR_MARKET"
    assert int(pipeline.get("scanner_candidates_count", 0)) == 0
    assert int(pipeline.get("order_intents_count", 0)) == 0
    assert pipeline.get("actual_order_submitted") is False
