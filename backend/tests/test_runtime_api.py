from __future__ import annotations

import asyncio
import time

import pytest
import main


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
def _isolate_runtime_state():
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


def test_runtime_tick_live_exposes_pipeline_summary_when_ready(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
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

    tick = _run(main.runtime_tick(mode="live", session="REGULAR_MARKET"))
    pipeline = ((tick.get("live") or {}).get("pipeline") or {})
    assert int(pipeline.get("scanner_candidates_count", 0)) == 0
    assert int(pipeline.get("order_intents_count", 0)) == 0
    assert int(pipeline.get("synthetic_candidates_count", 0)) >= 1
    assert int(pipeline.get("synthetic_order_intents_count", 0)) >= 1
    assert pipeline.get("live_pipeline_reason") in {"LIVE_SCANNER_NO_FRESH_DATA", "LIVE_SCANNER_NOT_CONNECTED"}
    assert pipeline.get("actual_order_submitted") is False


def test_runtime_tick_live_session_blocked_exposes_waiting_scanner_status(monkeypatch):
    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
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
