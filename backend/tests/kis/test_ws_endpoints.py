"""Tests for backend/kis/ws_endpoints.py — KIS WebSocket endpoint catalog."""
import pytest

from kis.ws_endpoints import (
    KIS_WS_ENDPOINTS,
    get_ws_endpoint,
    list_ws_endpoints,
    WsEndpoint,
)


class TestWsEndpointCatalog:
    """Endpoint catalog structure tests."""

    def test_all_required_endpoints_exist(self):
        required_tr_ids = {
            "H0STCNT0",   # 실시간 체결가
            "H0STASP0",   # 실시간 호가
            "H0STCNI0",   # 실시간 체결통보
            "H0STMKO0",   # 장운영정보
            "H0STANC0",   # 실시간 예상체결
        }
        catalog_ids = {e.tr_id for e in KIS_WS_ENDPOINTS}
        assert required_tr_ids <= catalog_ids, f"Missing: {required_tr_ids - catalog_ids}"

    def test_each_endpoint_has_required_fields(self):
        for ep in KIS_WS_ENDPOINTS:
            assert ep.name, f"Missing name for {ep.tr_id}"
            assert ep.tr_id, f"Missing tr_id"
            assert ep.channel_type, f"Missing channel_type for {ep.tr_id}"
            assert ep.source == "KIS_API_WS", f"Wrong source for {ep.tr_id}"

    def test_trade_tick_endpoint(self):
        ep = get_ws_endpoint("H0STCNT0")
        assert ep is not None
        assert ep.name == "실시간 체결가"
        assert ep.tr_id == "H0STCNT0"
        assert ep.channel_type == "realtime"
        assert ep.market == "KRX"

    def test_order_book_endpoint(self):
        ep = get_ws_endpoint("H0STASP0")
        assert ep is not None
        assert ep.name == "실시간 호가"
        assert ep.tr_id == "H0STASP0"
        assert ep.channel_type == "realtime"
        assert ep.market == "KRX"

    def test_fill_notice_endpoint(self):
        ep = get_ws_endpoint("H0STCNI0")
        assert ep is not None
        assert ep.name == "실시간 체결통보"
        assert ep.tr_id == "H0STCNI0"
        assert ep.channel_type == "notification"

    def test_market_status_endpoint(self):
        ep = get_ws_endpoint("H0STMKO0")
        assert ep is not None
        assert ep.name == "장운영정보"
        assert ep.tr_id == "H0STMKO0"
        assert ep.channel_type == "realtime"

    def test_expected_execution_endpoint(self):
        ep = get_ws_endpoint("H0STANC0")
        assert ep is not None
        assert ep.name == "실시간 예상체결"
        assert ep.tr_id == "H0STANC0"
        assert ep.channel_type == "realtime"

    def test_unknown_endpoint_returns_none(self):
        assert get_ws_endpoint("UNKNOWN_TR_ID") is None

    def test_list_all_endpoints(self):
        eps = list_ws_endpoints()
        assert len(eps) >= 5
        assert all(isinstance(e, WsEndpoint) for e in eps)

    def test_all_sources_are_kis_api_ws(self):
        for ep in KIS_WS_ENDPOINTS:
            assert ep.source == "KIS_API_WS"


class TestGetWsEndpoint:
    def test_get_by_tr_id(self):
        ep = get_ws_endpoint("H0STCNT0")
        assert ep is not None
        assert ep.tr_id == "H0STCNT0"
        assert ep.source == "KIS_API_WS"

    def test_none_for_empty_string(self):
        assert get_ws_endpoint("") is None

    def test_none_for_none(self):
        assert get_ws_endpoint(None) is None


class TestChannelTypes:
    def test_fill_notice_is_notification_type(self):
        ep = get_ws_endpoint("H0STCNI0")
        assert ep.channel_type == "notification"
