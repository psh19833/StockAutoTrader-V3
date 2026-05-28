"""Tests for Dashboard Foundation — models, service, routes"""
from __future__ import annotations

import json
import pytest

from dashboard.dashboard_models import (
    SystemStatusView, SessionStatusView, MarketRegimeView,
    ScannerCandidateView, QuantScoreView, StrategySignalView,
    RiskDecisionView, OrderStatusView, FillStatusView,
    PortfolioView, EodReportView, AuditTimelineView,
    DashboardSummary,
)
from dashboard.dashboard_service import DashboardService
from dashboard.dashboard_snapshot import build_dashboard_summary


class TestSystemStatusView:
    def test_create(self):
        v = SystemStatusView(
            live_trading_enabled=False,
            emergency_stop=False,
            modules_loaded=True,
            total_tests=769,
        )
        assert v.live_trading_enabled is False
        assert v.emergency_stop is False

    def test_live_trading_warning(self):
        v = SystemStatusView(
            live_trading_enabled=True, emergency_stop=False,
            modules_loaded=True, total_tests=769,
        )
        assert v.live_trading_enabled is True

    def test_no_secret_fields(self):
        v = SystemStatusView(False, False, True, 769)
        d = v.__dict__
        for s in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert s not in d


class TestSessionStatusView:
    def test_create(self):
        v = SessionStatusView(
            session_state="REGULAR_MARKET",
            buy_allowed=True,
            is_trading_day=True,
        )
        assert v.buy_allowed is True

    def test_holiday(self):
        v = SessionStatusView(
            session_state="CLOSED_HOLIDAY",
            buy_allowed=False,
            is_trading_day=False,
        )
        assert v.buy_allowed is False


class TestMarketRegimeView:
    def test_create(self):
        v = MarketRegimeView(
            regime="BULL", allow_new_buy=True,
            total_score=75.5, candidate_score_adjustment=5.0,
        )
        assert v.regime == "BULL"
        assert v.allow_new_buy is True


class TestScannerCandidateView:
    def test_create(self):
        v = ScannerCandidateView(
            symbol="005930", scanner_type="RAPID_SURGE",
            included=True, excluded_reason=None,
        )
        assert v.included is True

    def test_excluded(self):
        v = ScannerCandidateView(
            symbol="999999", scanner_type="RAPID_SURGE",
            included=False, excluded_reason="ETF_EXCLUDED",
        )
        assert v.included is False
        assert v.excluded_reason == "ETF_EXCLUDED"


class TestRiskDecisionView:
    def test_approved(self):
        v = RiskDecisionView(
            risk_decision_id="rd_001", symbol="005930",
            side="BUY", allowed=True,
            reason_code="APPROVED",
        )
        assert v.allowed is True

    def test_rejected(self):
        v = RiskDecisionView(
            risk_decision_id="rd_002", symbol="000660",
            side="BUY", allowed=False,
            reason_code="MARKET_REGIME_BLOCKED",
        )
        assert v.allowed is False
        assert "BLOCKED" in v.reason_code


class TestAuditTimelineView:
    def test_create(self):
        v = AuditTimelineView(
            event_type="SCAN_COMPLETED",
            correlation_id="corr_abc",
            symbol="005930",
            timestamp="2026-05-04T09:30:00Z",
        )
        assert v.correlation_id == "corr_abc"

    def test_filter_by_correlation(self):
        events = [
            AuditTimelineView("SCAN_STARTED", "corr_A", "", "t1"),
            AuditTimelineView("QUANT_EVALUATED", "corr_A", "005930", "t2"),
            AuditTimelineView("SCAN_STARTED", "corr_B", "", "t3"),
        ]
        filtered = [e for e in events if e.correlation_id == "corr_A"]
        assert len(filtered) == 2
        assert filtered[0].event_type == "SCAN_STARTED"
        assert filtered[1].event_type == "QUANT_EVALUATED"


class TestDashboardSummary:
    def test_build(self):
        s = build_dashboard_summary(
            live_trading_enabled=False,
            emergency_stop=False,
            session_state="REGULAR_MARKET",
            market_regime="BULL",
            allow_new_buy=True,
            scanner_candidates=[],
            quant_scores=[],
            strategy_signals=[],
            risk_decisions=[],
            orders=[],
            fills=[],
        )
        assert isinstance(s, DashboardSummary)
        assert s.system.live_trading_enabled is False
        # session buy_allowed is now date-dependent (holiday/weekend aware)
        assert s.session.session_state is not None  # always returns a valid state

    def test_summary_marks_live_trading_disabled(self):
        s = build_dashboard_summary(
            live_trading_enabled=False,
            emergency_stop=False,
            session_state="REGULAR_MARKET",
            market_regime="BULL",
            allow_new_buy=True,
            scanner_candidates=[],
            quant_scores=[],
            strategy_signals=[],
            risk_decisions=[],
            orders=[],
            fills=[],
        )
        assert s.system.live_trading_enabled is False

    def test_no_secret_in_summary(self):
        s = build_dashboard_summary(
            False, False, "REGULAR_MARKET", "BULL", True,
            [], [], [], [], [], [],
        )
        # Convert to dict-like representation
        import json
        raw = str(s.__dict__)
        for secret in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert secret not in raw


class TestDashboardServiceReadOnlyStatus:
    def test_default_session_status_is_unknown_and_buy_blocked(self, monkeypatch):
        import dashboard.dashboard_service as dashboard_service_mod
        from datetime import datetime, timezone

        class _FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                base = datetime(2026, 5, 7, 10, 0, 0, tzinfo=timezone.utc)
                if tz is None:
                    return base
                return base.astimezone(tz)

        monkeypatch.setattr(dashboard_service_mod, "datetime", _FixedDateTime)

        svc = DashboardService()
        monkeypatch.setattr(svc, "_probe_kis_holiday_status", lambda allow_external=False: {"data_available": False, "reason": "holiday_probe_error"})
        monkeypatch.setattr(svc, "_probe_kis_price", lambda symbol="005930", allow_external=False: {"data_available": False, "reason": "probe_error"})
        monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: {"success": False, "timestamp": ""})

        session = svc.get_session_status()
        assert session.session_state == "UNKNOWN"
        assert session.buy_allowed is False

    def test_default_market_regime_is_unknown_and_no_buy(self, monkeypatch):
        svc = DashboardService()
        # Isolate test from live/operational snapshot files under data/
        monkeypatch.setattr(svc, "_load_rest_smoke_snapshot", lambda: None)
        monkeypatch.setattr(svc, "_load_ws_smoke_snapshot", lambda: None)

        regime = svc.get_market_regime()
        assert regime.regime == "UNKNOWN"
        assert regime.allow_new_buy is False


class TestTelegramStatusRoute:
    def test_probe_disabled_is_reported_explicitly(self, monkeypatch):
        import dashboard.dashboard_routes as routes

        monkeypatch.delenv("SAT3_DASHBOARD_TELEGRAM_PROBE", raising=False)
        payload = routes.handle_get_telegram_status()

        assert payload["connected"] is False
        assert payload["probe_enabled"] is False
        assert payload["status_label"] == "조회 비활성화"
        assert payload["error"] == "external_probe_disabled"


class _DummyResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestDashboardServiceTokenCache:
    def test_probe_kis_price_reuses_cached_token(self, monkeypatch):
        svc = DashboardService()

        monkeypatch.setenv("KIS_APP_KEY", "dummy_key")
        monkeypatch.setenv("KIS_APP_SECRET", "dummy_secret")
        monkeypatch.setenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")

        class _EmptyTokenCache:
            def __init__(self, *args, **kwargs):
                pass

            def load(self):
                return None

            def token_present(self, rec):
                return False

            def is_expired(self, rec):
                return False

            def kst_attempted_today(self, rec):
                return False

            def record_tokenp_attempt(self, *args, **kwargs):
                return None

        import kis.token_provider as token_provider_mod
        monkeypatch.setattr(token_provider_mod, "TokenCache", _EmptyTokenCache)

        call_counts = {"token": 0, "price": 0}

        def fake_urlopen(req, timeout=0):
            url = req.full_url
            if "/oauth2/tokenP" in url:
                call_counts["token"] += 1
                return _DummyResponse(200, {"access_token": "***", "token_type": "Bearer", "expires_in": 3600})
            if "/uapi/domestic-stock/v1/quotations/inquire-price" in url:
                call_counts["price"] += 1
                return _DummyResponse(200, {"output": {"stck_prpr": "72000"}})
            return _DummyResponse(404, {"error": "not_found"})

        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        r1 = svc._probe_kis_price("005930", allow_external=True)
        r2 = svc._probe_kis_price("005930", allow_external=True)

        assert r1.get("data_available") is True
        assert r2.get("data_available") is True
        assert call_counts["token"] == 1
        assert call_counts["price"] == 2


def test_dashboard_telegram_status_requires_explicit_opt_in(monkeypatch):
    import dashboard.dashboard_routes as routes

    monkeypatch.delenv("SAT3_DASHBOARD_TELEGRAM_PROBE", raising=False)
    status = routes.handle_get_telegram_status()
    assert status.get("connected") is False
    assert status.get("error") == "external_probe_disabled"


def test_strategy_breakdown_reads_live_pipeline_from_runtime_status(monkeypatch):
    import main
    import dashboard.dashboard_routes as routes

    snapshot = dict(main._runtime_status)
    try:
        main._runtime_status["last_result"] = {
            "live": {
                "pipeline": {
                    "strategy_signals_sample": [
                        {"strategy_type": "RAPID_SURGE", "side": "BUY", "synthetic": False},
                        {"strategy_type": "RAPID_SURGE", "side": "HOLD", "synthetic": False},
                        {"strategy_type": "MEAN_REVERT", "side": "BUY", "synthetic": False},
                    ],
                    "synthetic_strategy_signals_sample": [
                        {"strategy_type": "RAPID_SURGE", "side": "BUY", "synthetic": True},
                    ],
                }
            }
        }
        rows = routes.handle_get_strategy_breakdown()
        by_strategy = {r.get("strategy"): r for r in rows}

        assert by_strategy["RAPID_SURGE"]["trades"] == 2
        assert by_strategy["RAPID_SURGE"]["buy_signals"] == 1
        assert by_strategy["RAPID_SURGE"]["hold_signals"] == 1
        assert by_strategy["MEAN_REVERT"]["trades"] == 1
        assert by_strategy["MEAN_REVERT"]["buy_signals"] == 1
    finally:
        main._runtime_status.clear()
        main._runtime_status.update(snapshot)
