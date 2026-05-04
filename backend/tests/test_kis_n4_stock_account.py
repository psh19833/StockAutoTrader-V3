"""Tests for N4-D: KIS Stock Info (product type, market, flags)"""
from __future__ import annotations
from kis.transport import StubTransport
from kis.stock_info_api import StockInfoApi


def _make_stub(**overrides):
    return StubTransport(responses=overrides)


class TestStockInfoApi:
    def test_kospi_common_stock(self):
        t = _make_stub(**{"/uapi/stock-info": {
            "output": {"market": "KOSPI", "product_type": "COMMON_STOCK"}
        }})
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("005930")
        assert result["market"] == "KOSPI"
        assert result["product_type"] == "COMMON_STOCK"

    def test_kosdaq_common_stock(self):
        t = _make_stub(**{"/uapi/stock-info": {
            "output": {"market": "KOSDAQ", "product_type": "COMMON_STOCK"}
        }})
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("035420")
        assert result["market"] == "KOSDAQ"

    def test_etf_excluded(self):
        t = _make_stub(**{"/uapi/stock-info": {
            "output": {"market": "KOSPI", "product_type": "ETF"}
        }})
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("999999")
        assert result["product_type"] == "ETF"

    def test_unknown_excluded(self):
        t = _make_stub(**{"/uapi/stock-info": {
            "output": {"market": "KOSPI", "product_type": "UNKNOWN"}
        }})
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("999999")
        assert result["product_type"] == "UNKNOWN"

    def test_management_issue_flag(self):
        t = _make_stub(**{"/uapi/stock-info": {
            "output": {"market": "KOSPI", "product_type": "COMMON_STOCK",
                       "is_management_issue": True}
        }})
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("005930")
        assert result["is_management_issue"] is True

    def test_source_metadata(self):
        t = _make_stub(**{"/uapi/stock-info": {
            "output": {"market": "KOSPI", "product_type": "COMMON_STOCK"}
        }})
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("005930")
        assert result["source"] == "KIS_API"
        assert "source_endpoints" in result

    def test_failure_data_unavailable(self):
        t = _make_stub()
        api = StockInfoApi(transport=t, base_url="https://test.com")
        result = api.get_stock_info("005930")
        assert result.get("data_available") is False


"""Tests for N4-E: KIS Account (balance, fills, PnL)"""
from kis.account_api import AccountApi

STUB_BALANCE = {
    "/uapi/balance": {
        "output": [
            {"pdno": "005930", "hldg_qty": "10", "pchs_avg_pric": "74000",
             "prpr": "75000"},
        ],
        "total_buyable": "5000000",
    }
}

STUB_FILLS = {
    "/uapi/fills": {
        "output": [
            {"odno": "ord_001", "pdno": "005930", "sll_buy_dvsn_cd": "02",
             "tot_ccld_qty": "10", "tot_ccld_amt": "750000",
             "rmn_qty": "0"},
        ]
    }
}


class TestAccountApi:
    def test_get_balance(self):
        t = _make_stub(**STUB_BALANCE)
        api = AccountApi(transport=t, base_url="https://test.com")
        result = api.get_balance()
        assert result["positions"]
        assert result["positions"][0]["symbol"] == "005930"
        assert result["positions"][0]["quantity"] == 10

    def test_get_fills(self):
        t = _make_stub(**STUB_FILLS)
        api = AccountApi(transport=t, base_url="https://test.com")
        result = api.get_fills()
        assert len(result) == 1
        assert result[0]["symbol"] == "005930"
        assert result[0]["filled_qty"] == 10

    def test_fill_has_remaining_qty(self):
        t = _make_stub(**{"/uapi/fills": {
            "output": [{"odno": "ord_001", "pdno": "005930",
                        "sll_buy_dvsn_cd": "02", "tot_ccld_qty": "5",
                        "tot_ccld_amt": "375000", "rmn_qty": "5"}]
        }})
        api = AccountApi(transport=t, base_url="https://test.com")
        result = api.get_fills()
        assert result[0]["remaining_qty"] == 5

    def test_no_order_submit(self):
        """AccountApi는 주문 제출을 하지 않는다"""
        t = _make_stub()
        api = AccountApi(transport=t, base_url="https://test.com")
        assert not hasattr(api, "submit_order")
        assert not hasattr(api, "place_order")

    def test_no_account_no_in_output(self):
        t = _make_stub(**STUB_BALANCE)
        api = AccountApi(transport=t, base_url="https://test.com")
        result = api.get_balance()
        assert "account_no" not in str(result)
