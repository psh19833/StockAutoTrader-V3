from __future__ import annotations

import dashboard.dashboard_routes as routes
import main


def test_summary_is_read_only_and_does_not_run_runtime_tick(monkeypatch):
    # If summary tries to run runtime tick, this test must fail.
    def _forbidden_tick(*args, **kwargs):
        raise AssertionError("summary must not call runtime tick")

    monkeypatch.setattr(routes, "run_runtime_tick_and_sync", _forbidden_tick)
    payload = routes.handle_get_summary(include_live_auto_ready=False)
    assert isinstance(payload, dict)
    assert "live_auto_ready" not in payload


def test_summary_live_auto_ready_uses_runtime_checks_source_of_truth(monkeypatch):
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
        "TELEGRAM_TARGET_VALID": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    monkeypatch.setattr(main, "_build_live_start_checks", lambda: (forced_checks, {"session": "CLOSED_AFTER_MARKET"}))

    payload = routes.handle_get_summary(include_live_auto_ready=True)
    assert payload["live_auto_ready"] is False
    assert "SESSION_REGULAR_MARKET" in payload.get("live_start_blockers", [])


def test_telegram_target_readiness_requires_explicit_target_verification(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "dummy")
    monkeypatch.delenv("SAT3_TELEGRAM_EXPLICIT_TARGET", raising=False)
    monkeypatch.delenv("SAT3_TELEGRAM_EXPLICIT_TARGET_OK", raising=False)

    valid, ctx = main._get_telegram_target_readiness()
    assert valid is False
    assert ctx["telegram_base_credentials"] is True
    assert ctx["telegram_explicit_target_ok"] is False

    monkeypatch.setenv("SAT3_TELEGRAM_EXPLICIT_TARGET", "telegram:SH P (dm)")
    monkeypatch.setenv("SAT3_TELEGRAM_EXPLICIT_TARGET_OK", "true")

    valid2, ctx2 = main._get_telegram_target_readiness()
    assert valid2 is True
    assert ctx2["telegram_explicit_target"] == "telegram:SH P (dm)"
