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
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: (forced_checks, {"session": "CLOSED_AFTER_MARKET"}))

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


def test_dashboard_summary_does_not_call_external_kis_or_telegram(monkeypatch):
    import urllib.request

    def _forbidden_urlopen(*args, **kwargs):
        raise AssertionError("external network call must not happen in dashboard summary")

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden_urlopen)
    payload = routes.handle_get_summary(include_live_auto_ready=False)
    assert isinstance(payload, dict)
    assert payload.get("session") is not None
    assert payload.get("data_router") is not None


def test_dashboard_summary_live_auto_ready_does_not_call_external_kis_or_telegram(monkeypatch):
    import urllib.request

    def _forbidden_urlopen(*args, **kwargs):
        raise AssertionError("external network call must not happen in dashboard summary")

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden_urlopen)
    payload = routes.handle_get_summary(include_live_auto_ready=True)
    assert isinstance(payload, dict)
    assert payload.get("session") is not None
    assert payload.get("data_router") is not None
    assert "live_auto_ready" in payload


def test_dashboard_summary_reports_read_only_current_readiness_without_snapshot_refresh(monkeypatch):
    import dashboard.dashboard_snapshot as snapshot_mod

    class _Status:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _FakeService:
        def __init__(self):
            self.refreshed = False

        def get_system_status(self):
            return _Status(live_trading_enabled=True, emergency_stop=False, modules_loaded=True, total_tests=1)

        def get_session_status(self):
            if self.refreshed:
                return _Status(session_state="REGULAR_MARKET", buy_allowed=True, is_trading_day=True, reason="refreshed")
            return _Status(session_state="UNKNOWN", buy_allowed=False, is_trading_day=False, reason="stale")

        def get_market_regime(self):
            if self.refreshed:
                return _Status(regime="NEUTRAL", allow_new_buy=True, total_score=55.0, candidate_score_adjustment=0.0, reason="refreshed")
            return _Status(regime="UNKNOWN", allow_new_buy=False, total_score=0.0, candidate_score_adjustment=0.0, reason="stale")

        def get_ws_status(self):
            if self.refreshed:
                return {"connection_state": "DISCONNECTED", "snapshot_fresh": True, "status_reason": "verified"}
            return {"connection_state": "UNKNOWN", "snapshot_fresh": False, "status_reason": "stale"}

        def get_data_router_status(self):
            if self.refreshed:
                return {"rest_available": True, "rest_snapshot_fresh": True, "ws_snapshot_fresh": True, "source": "KIS_API_REST"}
            return {"rest_available": False, "rest_snapshot_fresh": False, "ws_snapshot_fresh": False, "source": "KIS_API_REST"}

        def get_candidates(self):
            return []

        def get_quant_scores(self):
            return []

        def get_strategy_signals(self):
            return []

        def get_risk_decisions(self):
            return []

        def get_orders(self):
            return []

        def get_fills(self):
            return []

    fake_service = _FakeService()

    monkeypatch.setattr(routes, "get_service", lambda: fake_service)
    monkeypatch.setattr(snapshot_mod, "_service", fake_service)
    monkeypatch.setattr(main, "_build_live_start_checks", lambda refresh_snapshots=True: ({
        "LIVE_TRADING_ENABLED_TRUE": True,
        "CONFIRM_ENV_SET": True,
        "EMERGENCY_STOP_INACTIVE": True,
        "KIS_REST_AVAILABLE": fake_service.refreshed,
        "KIS_REST_FRESH": fake_service.refreshed,
        "KIS_WS_AVAILABLE": fake_service.refreshed,
        "KIS_WS_FRESH": fake_service.refreshed,
        "SESSION_REGULAR_MARKET": fake_service.refreshed,
        "MARKET_REGIME_KNOWN": fake_service.refreshed,
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": fake_service.refreshed,
        "RISK_LIMITS_LOADED": True,
        "TELEGRAM_TARGET_VALID": True,
        "AUDIT_LOGGING_ACTIVE": True,
        "FILL_RECONCILIATION_ACTIVE": True,
    }, {"session": "REGULAR_MARKET"}))

    payload = routes.handle_get_summary(include_live_auto_ready=True)
    assert payload["live_auto_ready"] is False
    assert "KIS_REST_AVAILABLE" in payload["live_start_blockers"]
    assert fake_service.refreshed is False
    assert getattr(payload["session"], "session_state") == "UNKNOWN"
    assert getattr(payload["market_regime"], "regime") == "UNKNOWN"
    assert payload["data_router"]["rest_snapshot_fresh"] is False
    assert payload["ws_status"]["snapshot_fresh"] is False
