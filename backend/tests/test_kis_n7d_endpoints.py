"""Tests for N7-D: KIS endpoint spec, TR_ID/params, catalog-based routing"""
from __future__ import annotations

import pytest
from kis.transport import StubTransport


class TestEndpointCatalog:
    """endpoint catalog에 read-only 스펙이 정의되어 있는지"""

    def test_current_price_has_path(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("domestic_stock_current_price")
        assert "inquire-price" in ep.path

    def test_current_price_has_tr_id(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("domestic_stock_current_price")
        assert ep.tr_id is not None

    def test_holiday_has_path(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("domestic_holiday")
        assert "holiday" in ep.path.lower()

    def test_orderbook_has_path(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("domestic_stock_orderbook")
        assert ep.tr_id is not None

    def test_stock_info_has_path(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("domestic_stock_basic_info")
        assert ep.path

    def test_balance_has_path(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("inquire_balance")
        assert "balance" in ep.path.lower()

    def test_fills_has_path(self):
        from kis.endpoints import get_endpoint
        ep = get_endpoint("inquire_ccnl")
        assert "ccnl" in ep.path.lower()


class TestKisClientTrIdParams:
    """KisClient가 TR_ID와 params를 지원하는지"""

    def test_client_get_json_with_params(self):
        from kis.client import KisClient
        from kis.auth import KisToken
        from datetime import datetime, timezone

        t = StubTransport(responses={
            "/uapi/domestic-stock/v1/quotations/inquire-price": {"output": {"stck_prpr": "75000"}}
        })
        client = KisClient(base_url="https://test.com", transport=t,
                           app_key="tk", app_secret="ts")
        client.auth_manager.set_token(KisToken("stub", "Bearer", 86400, datetime.now(timezone.utc)))
        resp = client.get_json(
            "domestic_stock_current_price",
            params={"FID_INPUT_ISCD": "005930", "FID_COND_MRKT_DIV_CODE": "J"}
        )
        assert resp.status_code == 200

    def test_client_get_json_resolves_endpoint(self):
        from kis.client import KisClient
        t = StubTransport(responses={
            "/uapi/domestic-stock/v1/quotations/inquire-price": {"ok": True}
        })
        client = KisClient(base_url="https://test.com", transport=t,
                           app_key="tk", app_secret="ts")
        from kis.auth import KisToken
        from datetime import datetime, timezone
        client.auth_manager.set_token(KisToken("x", "Bearer", 86400, datetime.now(timezone.utc)))
        resp = client.get_json("domestic_stock_current_price",
                               params={"FID_INPUT_ISCD": "005930", "FID_COND_MRKT_DIV_CODE": "J"})
        assert resp.status_code == 200

    def test_order_blocked_by_endpoint_name(self):
        from kis.client import KisClient
        from kis.errors import OrderEndpointBlockedError
        client = KisClient(base_url="https://test.com", transport=StubTransport(),
                           app_key="tk", app_secret="ts")
        with pytest.raises(OrderEndpointBlockedError):
            client.get_json("order_buy")


class TestMarketDataApiWithParams:
    """MarketDataApi가 실제 endpoint와 params를 사용하는지"""

    def test_get_current_price_uses_params(self):
        from kis.client import KisClient
        from kis.market_data_api import MarketDataApi
        from kis.auth import KisToken
        from datetime import datetime, timezone

        t = StubTransport(responses={
            "/uapi/domestic-stock/v1/quotations/inquire-price": {
                "output": {"stck_prpr": "75000"}
            }
        })
        client = KisClient(base_url="https://test.com", transport=t,
                           app_key="tk", app_secret="ts")
        client.auth_manager.set_token(KisToken("x", "Bearer", 86400, datetime.now(timezone.utc)))
        api = MarketDataApi(client=client)
        result = api.get_current_price("005930")
        assert result["current_price"] == 75000

    def test_order_blocked_by_path(self):
        from kis.client import KisClient
        from kis.errors import OrderEndpointBlockedError
        client = KisClient(base_url="https://test.com", transport=StubTransport(),
                           app_key="tk", app_secret="ts")
        with pytest.raises(OrderEndpointBlockedError):
            client.get_json("/uapi/domestic-stock/v1/trading/order-cash")


class TestSmokeDebugSafe:
    """smoke script debug 출력 안전성"""

    def test_no_raw_json_output(self):
        import scripts.kis_readonly_smoke as smoke
        source = __import__('pathlib').Path(smoke.__file__).read_text()
        assert "json.dumps" not in source or "safe" in source.lower()
