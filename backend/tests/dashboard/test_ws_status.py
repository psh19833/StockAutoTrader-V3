"""Tests for WebSocket Dashboard integration — ws_status in dashboard models."""
import pytest
from datetime import datetime, timezone

from dashboard.dashboard_models import (
    WebSocketStatusView,
    DashboardSummary,
    SystemStatusView,
    SessionStatusView,
    MarketRegimeView,
)
from kis.ws_models import WebSocketConnectionStatus


class TestWebSocketStatusView:
    def test_from_connection_status(self):
        now = datetime.now(timezone.utc)
        status = WebSocketConnectionStatus(
            connection_state="CONNECTED",
            subscribed_channels=["H0STCNT0", "H0STASP0"],
            last_message_at=now,
            reconnect_count=1,
            last_error_type=None,
            data_quality_warnings=[],
        )
        view = WebSocketStatusView.from_status(status)
        assert view.connection_state == "CONNECTED"
        assert view.subscribed_channels == ["H0STCNT0", "H0STASP0"]
        assert view.reconnect_count == 1
        assert view.last_error_type is None
        assert view.data_quality_warnings == []

    def test_from_disconnected_status(self):
        status = WebSocketConnectionStatus()
        view = WebSocketStatusView.from_status(status)
        assert view.connection_state == "DISCONNECTED"
        assert view.subscribed_channels == []
        assert view.reconnect_count == 0

    def test_all_fields_populated(self):
        now = datetime.now(timezone.utc)
        status = WebSocketConnectionStatus(
            connection_state="ERROR",
            subscribed_channels=["H0STCNT0"],
            last_message_at=now,
            reconnect_count=3,
            last_error_type="TIMEOUT",
            data_quality_warnings=["stale_data"],
        )
        view = WebSocketStatusView.from_status(status)
        assert view.connection_state == "ERROR"
        assert view.subscribed_channels == ["H0STCNT0"]
        assert view.last_message_at is not None
        assert view.reconnect_count == 3
        assert view.last_error_type == "TIMEOUT"
        assert "stale_data" in view.data_quality_warnings
        assert view.source == "KIS_API_WS"

    def test_does_not_contain_order_fields(self):
        """WS status view should never contain order-related fields."""
        status = WebSocketConnectionStatus()
        view = WebSocketStatusView.from_status(status)
        d = view.__dict__
        assert "buy" not in str(d).lower()
        assert "sell" not in str(d).lower()
        assert "order" not in str(d).lower()


class TestDashboardSummaryWithWebSocket:
    def test_summary_includes_ws_status(self):
        summary = DashboardSummary(
            system=SystemStatusView(
                live_trading_enabled=False,
                emergency_stop=False,
                modules_loaded=True,
                total_tests=926,
            ),
            session=SessionStatusView(
                session_state="REGULAR",
                buy_allowed=False,
                is_trading_day=True,
            ),
            market_regime=MarketRegimeView(
                regime="NORMAL",
                allow_new_buy=False,
                total_score=0.5,
                candidate_score_adjustment=0.0,
            ),
            scanner_summary={},
            quant_summary={},
            risk_summary={},
            order_summary={},
            fill_summary={},
            candidates=[],
            risk_decisions=[],
            data_sources={"market": "KIS_API"},
            ws_status=WebSocketStatusView(
                connection_state="CONNECTED",
                subscribed_channels=["H0STCNT0"],
                reconnect_count=0,
            ),
        )
        assert summary.ws_status is not None
        assert summary.ws_status.connection_state == "CONNECTED"
        assert "H0STCNT0" in summary.ws_status.subscribed_channels

    def test_summary_optional_ws_status(self):
        """ws_status can be None (backward compatibility)."""
        summary = DashboardSummary(
            system=SystemStatusView(
                live_trading_enabled=False,
                emergency_stop=False,
                modules_loaded=True,
                total_tests=926,
            ),
            session=SessionStatusView(
                session_state="REGULAR",
                buy_allowed=False,
                is_trading_day=True,
            ),
            market_regime=MarketRegimeView(
                regime="NORMAL",
                allow_new_buy=False,
                total_score=0.5,
                candidate_score_adjustment=0.0,
            ),
            scanner_summary={},
            quant_summary={},
            risk_summary={},
            order_summary={},
            fill_summary={},
            candidates=[],
            risk_decisions=[],
            data_sources={"market": "KIS_API"},
        )
        assert summary.ws_status is None
