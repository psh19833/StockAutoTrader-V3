"""KIS Stock Info API — 종목정보/상품유형"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class StockInfoApi:
    def __init__(self, transport: KisTransport | StubTransport, base_url: str):
        self._transport = transport
        self._base_url = base_url

    def get_stock_info(self, symbol: str) -> dict:
        resp = self._transport.get_json("/uapi/stock-info")
        if resp.status_code != 200 or "output" not in resp.body:
            return {"symbol": symbol, "data_available": False,
                    "source": "KIS_API", "source_endpoints": ()}
        out = resp.body["output"]
        return {
            "symbol": symbol,
            "market": out.get("market", "UNKNOWN"),
            "product_type": out.get("product_type", "UNKNOWN"),
            "is_management_issue": out.get("is_management_issue", False),
            "is_investment_warning": out.get("is_investment_warning", False),
            "is_trading_halted": out.get("is_trading_halted", False),
            "source": "KIS_API",
            "source_endpoints": ("kis/stock-info",),
            "data_available": True,
        }
