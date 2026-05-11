from __future__ import annotations

from datetime import datetime, timedelta, timezone

import main
from dashboard.dashboard_models import MarketRegimeView, SessionStatusView
from dashboard.dashboard_routes import get_service
from dashboard.dashboard_service import DashboardService
import dashboard.dashboard_service as dashboard_service_mod


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = datetime(2026, 5, 7, 10, 0, 0, tzinfo=timezone.utc)
        if tz is None:
            return base
        return base.astimezone(tz)


def _fresh_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()


# PHASE 1: SESSION_REGULAR_MARKET

def test_session_kis_source_success_regular_market(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_holiday_status", lambda allow_external=False: {"data_available": True, "is_holiday": False, "open_flag": "Y"})
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": True, "current_price": 100})
    monkeypatch.setattr(svc, "_is_kst_regular_market_window", lambda: True)

    st = svc.get_session_status()
    assert st.session_state == "REGULAR_MARKET"
    assert st.reason == "session_source=KIS_MARKET_STATUS"


def test_session_fallback_kst_and_rest_verified_regular_market(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(dashboard_service_mod, "datetime", _FixedDateTime)
    monkeypatch.setattr(svc, "_probe_kis_holiday_status", lambda allow_external=False: {"data_available": False, "reason": "holiday_probe_error"})
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": True, "current_price": 100})
    monkeypatch.setattr(svc, "_is_kst_regular_market_window", lambda: True)
    monkeypatch.setattr(svc, "get_ws_status", lambda: {"status_reason": "ws_status_provider_not_configured", "connection_state": "UNKNOWN"})
    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {"success": True, "timestamp": _fresh_ts()})

    st = svc.get_session_status()
    assert st.session_state == "REGULAR_MARKET"
    assert st.reason == "session_source=KST_TIME_WITH_REST_VERIFIED"


def test_session_fallback_regular_market_without_probe_when_rest_or_ws_verified(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(dashboard_service_mod, "datetime", _FixedDateTime)
    monkeypatch.setattr(svc, "_probe_kis_holiday_status", lambda allow_external=False: {"data_available": False, "reason": "holiday_probe_error"})
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "external_probe_disabled"})
    monkeypatch.setattr(svc, "_is_kst_regular_market_window", lambda: True)
    monkeypatch.setattr(svc, "get_ws_status", lambda: {"status_reason": "ws_readonly_smoke_verified", "connection_state": "DISCONNECTED"})
    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {"success": True, "timestamp": _fresh_ts()})

    st = svc.get_session_status()
    assert st.session_state == "REGULAR_MARKET"
    assert st.reason == "session_source=KST_TIME_WITH_REST_VERIFIED"


def test_session_weekend_or_outside_hours_closed(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_holiday_status", lambda allow_external=False: {"data_available": True, "is_holiday": False, "open_flag": "Y"})
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": True, "current_price": 100})
    monkeypatch.setattr(svc, "_is_kst_regular_market_window", lambda: False)

    st = svc.get_session_status()
    assert st.session_state == "CLOSED_AFTER_MARKET"


def test_session_source_unavailable_keeps_unknown(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(dashboard_service_mod, "datetime", _FixedDateTime)
    monkeypatch.setattr(svc, "_probe_kis_holiday_status", lambda allow_external=False: {"data_available": False, "reason": "holiday_probe_error"})
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})
    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {"success": False, "timestamp": _fresh_ts()})

    st = svc.get_session_status()
    assert st.session_state == "UNKNOWN"


# PHASE 2: MARKET_REGIME_KNOWN

def test_market_regime_known_from_fresh_snapshot(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})
    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {
        "success": True,
        "timestamp": _fresh_ts(),
        "observed_at": _fresh_ts(),
        "change_rate": 0.4,
        "last_price": 100,
    })

    regime = svc.get_market_regime()
    assert regime.regime in {"BULL", "BEAR", "NEUTRAL"}
    assert regime.regime != "UNKNOWN"
    assert regime.reason == "market_regime_source=REST_SMOKE_SNAPSHOT"


def test_market_regime_unknown_when_snapshot_stale(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})
    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {
        "success": True,
        "timestamp": _stale_ts(),
        "change_rate": 0.4,
    })

    regime = svc.get_market_regime()
    assert regime.regime == "UNKNOWN"
    assert regime.reason == "market_regime_snapshot_stale_or_invalid"


def test_market_regime_unknown_when_change_rate_missing(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})
    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {
        "success": True,
        "timestamp": _fresh_ts(),
    })

    regime = svc.get_market_regime()
    assert regime.regime == "UNKNOWN"
    assert regime.reason == "market_regime_feed_partial"


# PHASE 3: RISK_LIMITS_LOADED

def test_risk_limits_loaded_requires_all_keys_and_types(monkeypatch):
    monkeypatch.setenv("SAT3_MAX_DAILY_LOSS_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_POSITION_COUNT", "3")
    monkeypatch.setenv("SAT3_MAX_ORDER_AMOUNT_KRW", "50000")
    monkeypatch.setenv("SAT3_MAX_AMOUNT_PER_SYMBOL_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_PENDING_ORDERS", "1")
    monkeypatch.setenv("SAT3_DUPLICATE_ORDER_GUARD_ENABLED", "true")

    loaded, missing = main._risk_limits_loaded()
    assert loaded is True
    assert missing == []


def test_risk_limits_missing_or_invalid_blocks(monkeypatch):
    monkeypatch.setenv("SAT3_MAX_DAILY_LOSS_KRW", "-1")
    monkeypatch.setenv("SAT3_MAX_POSITION_COUNT", "abc")
    monkeypatch.delenv("SAT3_MAX_ORDER_AMOUNT_KRW", raising=False)
    monkeypatch.setenv("SAT3_MAX_AMOUNT_PER_SYMBOL_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_PENDING_ORDERS", "0")
    monkeypatch.setenv("SAT3_DUPLICATE_ORDER_GUARD_ENABLED", "")

    loaded, missing = main._risk_limits_loaded()
    assert loaded is False
    assert "SAT3_MAX_DAILY_LOSS_KRW" in missing
    assert "SAT3_MAX_POSITION_COUNT" in missing
    assert "SAT3_MAX_ORDER_AMOUNT_KRW" in missing
    assert "SAT3_MAX_PENDING_ORDERS" in missing
    assert "SAT3_DUPLICATE_ORDER_GUARD_ENABLED" in missing


# PHASE 4: LIVE/CONFIRM manual gates

def test_live_confirm_gate_matrix(monkeypatch):
    svc = get_service()
    svc.inject_session_status(SessionStatusView(session_state="REGULAR_MARKET", buy_allowed=True, is_trading_day=True))
    svc.inject_market_regime(MarketRegimeView(regime="NEUTRAL", allow_new_buy=True, total_score=55.0, candidate_score_adjustment=0.0))

    # risk limits OK
    monkeypatch.setenv("SAT3_MAX_DAILY_LOSS_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_POSITION_COUNT", "3")
    monkeypatch.setenv("SAT3_MAX_ORDER_AMOUNT_KRW", "50000")
    monkeypatch.setenv("SAT3_MAX_AMOUNT_PER_SYMBOL_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_PENDING_ORDERS", "1")
    monkeypatch.setenv("SAT3_DUPLICATE_ORDER_GUARD_ENABLED", "true")

    # none set
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.delenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", raising=False)
    checks, _ = main._build_live_start_checks()
    assert checks["LIVE_TRADING_ENABLED_TRUE"] is False
    assert checks["CONFIRM_ENV_SET"] is False

    # live only
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.delenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", raising=False)
    checks, _ = main._build_live_start_checks()
    assert checks["LIVE_TRADING_ENABLED_TRUE"] is True
    assert checks["CONFIRM_ENV_SET"] is False

    # confirm only
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", "CONFIRM_LIVE_AUTO_TRADING")
    checks, _ = main._build_live_start_checks()
    assert checks["LIVE_TRADING_ENABLED_TRUE"] is False
    assert checks["CONFIRM_ENV_SET"] is True

    # both
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", "CONFIRM_LIVE_AUTO_TRADING")
    checks, _ = main._build_live_start_checks()
    assert checks["LIVE_TRADING_ENABLED_TRUE"] is True
    assert checks["CONFIRM_ENV_SET"] is True


def test_rest_snapshot_freshness_hard_check(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})

    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {
        "success": True,
        "price": "OK",
        "timestamp": _fresh_ts(),
        "sample_price": 70000,
    })
    router_fresh = svc.get_data_router_status()
    assert router_fresh["rest_snapshot_fresh"] is True
    assert router_fresh["rest_available"] is True

    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {
        "success": True,
        "price": "OK",
        "timestamp": _stale_ts(),
        "sample_price": 70000,
    })
    router_stale = svc.get_data_router_status()
    assert router_stale["rest_snapshot_fresh"] is False
    assert router_stale["rest_available"] is False


def test_ws_snapshot_freshness_hard_check(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_load_ws_smoke_snapshot", lambda: {
        "success": True,
        "timestamp": _fresh_ts(),
        "connection_state": "CONNECTED",
        "channels": ["H0STCNT0"],
    })
    ws_fresh = svc.get_ws_status()
    assert ws_fresh["snapshot_fresh"] is True
    assert ws_fresh["status_reason"] == "ws_readonly_smoke_verified"

    monkeypatch.setattr(svc, "_load_ws_smoke_snapshot", lambda: {
        "success": True,
        "timestamp": _stale_ts(),
        "connection_state": "CONNECTED",
        "channels": ["H0STCNT0"],
    })
    ws_stale = svc.get_ws_status()
    assert ws_stale["snapshot_fresh"] is False
    assert ws_stale["status_reason"] == "ws_readonly_smoke_stale"


def test_invalid_or_missing_snapshot_timestamp_treated_as_stale(monkeypatch):
    svc = DashboardService()
    monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})

    monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {"success": True, "price": "OK", "timestamp": "invalid-ts"})
    rest_invalid = svc.get_data_router_status()
    assert rest_invalid["rest_snapshot_fresh"] is False

    monkeypatch.setattr(svc, "_load_ws_smoke_snapshot", lambda: {"success": True})
    ws_missing_ts = svc.get_ws_status()
    assert ws_missing_ts["snapshot_fresh"] is False


def test_live_readiness_requires_fresh_rest_and_ws_evidence(monkeypatch):
    import dashboard.dashboard_routes as routes

    class _DummyService:
        def get_system_status(self):
            class _S:
                live_trading_enabled = True
            return _S()

    monkeypatch.setattr(routes, "get_service", lambda: _DummyService())
    monkeypatch.setattr(routes, "handle_get_summary", lambda include_live_auto_ready=False: {
        "session": type("Session", (), {"session_state": "REGULAR_MARKET", "reason": "session_source=KST_TIME_WITH_REST_VERIFIED"})(),
        "market_regime": type("Regime", (), {"regime": "NEUTRAL", "reason": "market_regime_source=REST_SMOKE_SNAPSHOT"})(),
        "data_router": {"rest_available": True, "rest_snapshot_fresh": False},
        "ws_status": {"connection_state": "UNKNOWN", "snapshot_fresh": False, "status_reason": "ws_readonly_smoke_stale"},
        "portfolio_stale": False,
        "portfolio_source_of_truth": "KIS_REST",
    })

    monkeypatch.setenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", "CONFIRM_LIVE_AUTO_TRADING")
    monkeypatch.setenv("SAT3_MAX_DAILY_LOSS_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_POSITION_COUNT", "3")
    monkeypatch.setenv("SAT3_MAX_ORDER_AMOUNT_KRW", "50000")
    monkeypatch.setenv("SAT3_MAX_AMOUNT_PER_SYMBOL_KRW", "100000")
    monkeypatch.setenv("SAT3_MAX_PENDING_ORDERS", "1")
    monkeypatch.setenv("SAT3_DUPLICATE_ORDER_GUARD_ENABLED", "true")
    monkeypatch.setenv("SAT3_TELEGRAM_EXPLICIT_TARGET", "telegram:dummy")
    monkeypatch.setenv("SAT3_TELEGRAM_EXPLICIT_TARGET_OK", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "dummy")

    checks, _ = main._build_live_start_checks()
    assert checks["KIS_REST_AVAILABLE"] is True
    assert checks["KIS_REST_FRESH"] is False
    assert checks["KIS_WS_AVAILABLE"] is False
    assert checks["KIS_WS_FRESH"] is False
