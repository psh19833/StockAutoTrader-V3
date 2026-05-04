"""Tests for N6: RealTransport + Query Facade + KIS Error Handling"""
from __future__ import annotations

import pytest
from kis.transport import StubTransport, TransportResponse
from kis.errors import (
    OrderEndpointBlockedError, NetworkError, TimeoutError as KisTimeoutError,
)
from kis.client import KisClient
from kis.query_facade import KisQueryFacade


# ── Stub Transport with error simulation ──

class ErrorStubTransport:
    """Simulates network errors for testing error handling"""
    def __init__(self, error_type: str = "timeout"):
        self._error = error_type
        self.calls: list = []

    def get_json(self, path, params=None):
        self.calls.append(("GET", path))
        if self._error == "timeout":
            raise KisTimeoutError("Connection timed out")
        elif self._error == "network":
            raise NetworkError("Network unreachable")
        elif self._error == "bad_json":
            return TransportResponse(200, {}, {"content-type": "text/html"})
        elif self._error == "http_500":
            return TransportResponse(500, {"error": "server_error"})
        return TransportResponse(200, {"output": {}})

    def post_json(self, path, json_data=None):
        self.calls.append(("POST", path))
        if self._error == "timeout":
            raise KisTimeoutError("Connection timed out")
        return TransportResponse(200, {"output": {}})


class TestKisErrors:
    def test_order_endpoint_blocked_error(self):
        err = OrderEndpointBlockedError("/uapi/domestic-stock/v1/trading/order-cash")
        assert "order" in str(err).lower()

    def test_network_error(self):
        err = NetworkError("unreachable")
        assert isinstance(err, Exception)

    def test_timeout_error(self):
        err = KisTimeoutError("timed out")
        assert isinstance(err, Exception)


class TestClientOrderBlocking:
    def test_order_endpoint_blocked(self):
        transport = StubTransport()
        client = KisClient(
            base_url="https://test.com",
            transport=transport,
            app_key="test", app_secret="test",
        )
        with pytest.raises(OrderEndpointBlockedError):
            client.get_json("/uapi/domestic-stock/v1/trading/order-cash")

    def test_non_order_endpoint_allowed(self):
        transport = StubTransport(responses={"/uapi/price": {"output": {"prpr": "75000"}}})
        client = KisClient(
            base_url="https://test.com",
            transport=transport,
            app_key="test", app_secret="test",
        )
        resp = client.get_json("/uapi/price")
        assert resp.status_code == 200

    def test_post_order_blocked(self):
        transport = StubTransport()
        client = KisClient(
            base_url="https://test.com",
            transport=transport,
            app_key="test", app_secret="test",
        )
        with pytest.raises(OrderEndpointBlockedError):
            client.post_json("/uapi/domestic-stock/v1/trading/order-cash", {})


class TestQueryFacade:
    def test_facade_exposes_read_only_apis(self):
        transport = StubTransport(responses={
            "/uapi/price": {"output": {"stck_prpr": "75000"}},
            "/uapi/stock-info": {"output": {"market": "KOSPI", "product_type": "COMMON_STOCK"}},
        })
        client = KisClient(
            base_url="https://test.com", transport=transport,
            app_key="test", app_secret="test",
        )
        facade = KisQueryFacade(client=client)

        price = facade.get_current_price("005930")
        assert price["current_price"] == 75000

        info = facade.get_stock_info("005930")
        assert info["market"] == "KOSPI"

    def test_facade_has_no_order_methods(self):
        facade = KisQueryFacade(client=None)
        assert not hasattr(facade, "submit_order")
        assert not hasattr(facade, "place_order")
        assert not hasattr(facade, "buy_order")
        assert not hasattr(facade, "sell_order")

    def test_facade_data_unavailable(self):
        transport = ErrorStubTransport(error_type="timeout")
        client = KisClient(
            base_url="https://test.com", transport=transport,
            app_key="test", app_secret="test",
        )
        facade = KisQueryFacade(client=client)
        result = facade.get_current_price("005930")
        assert result.get("data_available") is False


class TestErrorHandling:
    def test_timeout_handling(self):
        transport = ErrorStubTransport(error_type="timeout")
        client = KisClient(
            base_url="https://test.com", transport=transport,
            app_key="test", app_secret="test",
        )
        facade = KisQueryFacade(client=client)
        result = facade.get_current_price("005930")
        assert result.get("data_available") is False

    def test_network_error_handling(self):
        transport = ErrorStubTransport(error_type="network")
        client = KisClient(
            base_url="https://test.com", transport=transport,
            app_key="test", app_secret="test",
        )
        facade = KisQueryFacade(client=client)
        result = facade.get_stock_info("005930")
        assert result.get("data_available") is False

    def test_http_500_handling(self):
        transport = ErrorStubTransport(error_type="http_500")
        client = KisClient(
            base_url="https://test.com", transport=transport,
            app_key="test", app_secret="test",
        )
        resp = client.get_json("/uapi/price")
        assert resp.status_code == 500


class TestNoRealNetworkInTests:
    def test_no_requests_import_in_test(self):
        """테스트 코드에 requests/httpx import 금지"""
        import sys
        for mod_name in ["requests", "httpx", "urllib3"]:
            assert mod_name not in sys.modules or "test" in str(sys.modules.get(mod_name, ""))
