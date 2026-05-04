"""Tests for N4-C: KIS Market Data (price, orderbook, execution)"""
from __future__ import annotations
from kis.transport import StubTransport
from kis.market_data_api import MarketDataApi


def _make_stub(**overrides):
    return StubTransport(responses=overrides)


class TestMarketDataApi:
    def test_get_current_price(self):
        t = _make_stub(**{"/uapi/price": {
            "output": {"stck_prpr": "75000", "stck_oprc": "74000",
                       "stck_hgpr": "76000", "stck_lwpr": "73500"}
        }})
        api = MarketDataApi(transport=t, base_url="https://test.com")
        result = api.get_current_price("005930")
        assert result["current_price"] == 75000
        assert result["open_price"] == 74000
        assert result["high_price"] == 76000

    def test_get_orderbook(self):
        t = _make_stub(**{"/uapi/orderbook": {
            "output": {"ask_price": "75100", "bid_price": "74900"}
        }})
        api = MarketDataApi(transport=t, base_url="https://test.com")
        result = api.get_orderbook("005930")
        assert result["ask_price"] == 75100
        assert result["bid_price"] == 74900

    def test_get_execution_strength(self):
        t = _make_stub(**{"/uapi/execution": {
            "output": {"execution_strength": "150.0", "volume": "10000000"}
        }})
        api = MarketDataApi(transport=t, base_url="https://test.com")
        result = api.get_execution_strength("005930")
        assert result["execution_strength"] == 150.0
        assert result["volume"] == 10000000

    def test_failure_returns_data_unavailable(self):
        t = _make_stub(**{"/uapi/price": {"error": "timeout"}})
        api = MarketDataApi(transport=t, base_url="https://test.com")
        result = api.get_current_price("005930")
        assert result.get("data_available") is False

    def test_source_metadata(self):
        t = _make_stub(**{"/uapi/price": {
            "output": {"stck_prpr": "50000"}
        }})
        api = MarketDataApi(transport=t, base_url="https://test.com")
        result = api.get_current_price("005930")
        assert result["source"] == "KIS_API"
        assert "source_endpoints" in result

    def test_no_fake_prices(self):
        """API 실패 시에도 임의 가격 생성 금지"""
        t = _make_stub()
        api = MarketDataApi(transport=t, base_url="https://test.com")
        result = api.get_current_price("005930")
        assert result.get("data_available") is False
        assert "current_price" not in result or result.get("current_price") == 0
