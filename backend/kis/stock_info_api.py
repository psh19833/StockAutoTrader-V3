"""KIS Stock Info API — 종목정보/상품유형"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport

_INFO_PATH = "/uapi/domestic-stock/v1/quotations/inquire-stock-basic-info"


class StockInfoApi:
    def __init__(self, transport=None, base_url: str = "", client=None):
        self._transport = transport
        self._base_url = base_url
        self._client = client

    def _get_output(self, body: dict) -> dict:
        for key in ("output", "output1", "output2"):
            if key in body and isinstance(body[key], dict):
                return body[key]
        return {}

    def get_stock_info(self, symbol: str) -> dict:
        if self._client:
            resp = self._client.get_json("domestic_stock_basic_info",
                                         params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol})
        elif self._transport:
            resp = self._transport.get_json(_INFO_PATH)
        else:
            return {"symbol": symbol, "data_available": False, "source": "KIS_API", "source_endpoints": ()}
        if resp.status_code != 200:
            return {"symbol": symbol, "data_available": False, "source": "KIS_API", "source_endpoints": ()}
        out = self._get_output(resp.body)
        if not out:
            return {"symbol": symbol, "data_available": False, "source": "KIS_API", "source_endpoints": ()}
        market = out.get("market", out.get("mrkt_div_cls_cd", out.get("mrkt_cls", "UNKNOWN")))
        pt = out.get("product_type", out.get("prdt_type_cd", out.get("std_pdno_tp", "UNKNOWN")))
        return {"symbol": symbol, "market": str(market), "product_type": str(pt),
                "is_management_issue": bool(out.get("is_management_issue", False)),
                "is_investment_warning": bool(out.get("is_investment_warning", False)),
                "is_trading_halted": bool(out.get("is_trading_halted", False)),
                "source": "KIS_API", "source_endpoints": ("kis/stock-info",), "data_available": True}
