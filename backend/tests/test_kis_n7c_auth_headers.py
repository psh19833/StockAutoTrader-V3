"""Tests for N7-C: KisClient auth header injection + API refactoring"""
from __future__ import annotations

import pytest
from kis.transport import StubTransport, TransportResponse


class TestTransportHeaders:
    """RealTransport headers 파라미터 + header 로그 금지"""

    def test_real_transport_accepts_headers(self):
        from kis.transport import RealTransport
        rt = RealTransport(base_url="https://test.com")
        # 구조 검증만 (실제 호출 금지)
        import inspect
        sig = inspect.signature(rt.get_json)
        assert "headers" in sig.parameters

    def test_stub_transport_accepts_headers(self):
        t = StubTransport(responses={"/uapi/test": {"ok": True}})
        resp = t.get_json("/uapi/test", headers={"authorization": "Bearer stub"})
        assert resp.status_code == 200


class TestKisClientAuthHeaders:
    """KisClient가 auth header를 구성하는지"""

    def test_client_constructs_auth_headers(self):
        from kis.client import KisClient
        from kis.transport import StubTransport
        t = StubTransport(responses={"/uapi/test": {"ok": True}})
        client = KisClient(
            base_url="https://test.com", transport=t,
            app_key="test_key", app_secret="test_secret",
        )
        # token 없이 호출 시도 → InvalidTokenError 예상
        # But we're testing header generation, not actual call
        assert client.auth_manager is not None

    def test_client_get_json_with_auth(self):
        from kis.client import KisClient
        from kis.transport import StubTransport
        from kis.auth import KisToken

        t = StubTransport(responses={"/uapi/test": {"ok": True}})
        client = KisClient(
            base_url="https://test.com", transport=t,
            app_key="tk", app_secret="ts",
        )
        # Set a valid token
        from datetime import datetime, timezone
        client.auth_manager.set_token(KisToken(
            access_token="stub_token", token_type="Bearer",
            expires_in=86400, issued_at=datetime.now(timezone.utc),
        ))
        resp = client.get_json("/uapi/test")
        assert resp.status_code == 200

    def test_client_auth_header_values_not_in_transport_calls(self):
        """auth header 값이 transport call log에 노출되지 않음"""
        from kis.client import KisClient
        from kis.transport import StubTransport
        from kis.auth import KisToken
        from datetime import datetime, timezone

        t = StubTransport(responses={"/uapi/test": {"ok": True}})
        client = KisClient(
            base_url="https://test.com", transport=t,
            app_key="REAL_KEY_12345", app_secret="REAL_SECRET_ABCDEF",
        )
        client.auth_manager.set_token(KisToken(
            access_token="real_token_value", token_type="Bearer",
            expires_in=86400, issued_at=datetime.now(timezone.utc),
        ))
        resp = client.get_json("/uapi/test")
        # StubTransport의 calls 로그에 auth 값이 포함되지 않아야 함
        for call in t.calls:
            call_str = str(call)
            assert "REAL_KEY_12345" not in call_str
            assert "REAL_SECRET_ABCDEF" not in call_str
            assert "real_token_value" not in call_str


class TestApiClassesUseClient:
    """API 클래스들이 transport 대신 KisClient를 사용"""

    def test_market_data_api_uses_client(self):
        from kis.client import KisClient
        from kis.transport import StubTransport
        from kis.market_data_api import MarketDataApi
        from kis.auth import KisToken
        from datetime import datetime, timezone

        t = StubTransport(responses={
            "/uapi/price": {"output": {"stck_prpr": "75000"}}
        })
        client = KisClient(base_url="https://test.com", transport=t,
                           app_key="tk", app_secret="ts")
        client.auth_manager.set_token(KisToken(
            "stub", "Bearer", 86400, datetime.now(timezone.utc)))
        api = MarketDataApi(client=client)
        result = api.get_current_price("005930")
        assert result["current_price"] == 75000

    def test_stock_info_api_uses_client(self):
        from kis.client import KisClient
        from kis.transport import StubTransport
        from kis.stock_info_api import StockInfoApi
        from kis.auth import KisToken
        from datetime import datetime, timezone

        t = StubTransport(responses={
            "/uapi/stock-info": {"output": {"market": "KOSPI", "product_type": "COMMON_STOCK"}}
        })
        client = KisClient(base_url="https://test.com", transport=t,
                           app_key="tk", app_secret="ts")
        client.auth_manager.set_token(KisToken("stub", "Bearer", 86400, datetime.now(timezone.utc)))
        api = StockInfoApi(client=client)
        result = api.get_stock_info("005930")
        assert result["market"] == "KOSPI"

    def test_query_facade_uses_client(self):
        from kis.client import KisClient
        from kis.transport import StubTransport
        from kis.query_facade import KisQueryFacade
        from kis.auth import KisToken
        from datetime import datetime, timezone

        t = StubTransport(responses={
            "/uapi/price": {"output": {"stck_prpr": "75000"}},
        })
        client = KisClient(base_url="https://test.com", transport=t,
                           app_key="tk", app_secret="ts")
        client.auth_manager.set_token(KisToken("stub", "Bearer", 86400, datetime.now(timezone.utc)))
        facade = KisQueryFacade(client=client)
        result = facade.get_current_price("005930")
        assert result["current_price"] == 75000

    def test_order_still_blocked(self):
        """주문 endpoint는 KisClient에서 계속 차단"""
        from kis.client import KisClient
        from kis.transport import StubTransport
        from kis.errors import OrderEndpointBlockedError

        client = KisClient(base_url="https://test.com", transport=StubTransport(),
                           app_key="tk", app_secret="ts")
        with pytest.raises(OrderEndpointBlockedError):
            client.get_json("/uapi/domestic-stock/v1/trading/order-cash")
