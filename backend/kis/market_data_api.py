"""KIS Market Data API — 현재가, 호가, 체결강도"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport

_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
_ORDERBOOK_PATH = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
_EXEC_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-ccnl"


class MarketDataApi:
    def __init__(self, transport=None, base_url: str = "", client=None):
        self._transport = transport
        self._base_url = base_url
        self._client = client

    def _get(self, endpoint_name: str, fallback_path: str, params: dict | None = None) -> dict:
        if self._client:
            resp = self._client.get_json(endpoint_name, params=params)
        elif self._transport:
            resp = self._transport.get_json(fallback_path, params=params)
        else:
            return {}
        if resp.status_code != 200:
            return {}
        for key in ("output", "output1", "output2"):
            if key in resp.body and isinstance(resp.body[key], dict):
                return resp.body[key]
        return {}

    def get_current_price(self, symbol: str) -> dict:
        out = self._get("domestic_stock_current_price", _PRICE_PATH,
                        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol})
        if not out:
            return {"symbol": symbol, "data_available": False,
                    "source": "KIS_API", "source_endpoints": ()}
        price_keys = ("stck_prpr", "prpr", "current_price", "last_price")
        price = 0
        for k in price_keys:
            if k in out:
                price = _int(out[k])
                break
        change_rate = _float(out.get("prdy_ctrt", out.get("change_rate", out.get("chg_rate", 0))))

        # Accumulated volume/trading value fields (KIS inquire-price)
        # acml_vol: 누적거래량, acml_tr_pbmn: 누적거래대금
        acc_volume = _int(out.get("acml_vol", out.get("accumulated_volume", 0)))
        acc_trading_value = _int(out.get("acml_tr_pbmn", out.get("accumulated_trading_value", 0)))
        change_price = _int(out.get("prdy_vrss", out.get("change_price", 0)))

        return {"symbol": symbol, "current_price": price,
                "open_price": _int(out.get("stck_oprc", out.get("oprc", 0))),
                "high_price": _int(out.get("stck_hgpr", out.get("hgpr", 0))),
                "low_price": _int(out.get("stck_lwpr", out.get("lwpr", 0))),
                "accumulated_volume": acc_volume,
                "accumulated_trading_value": acc_trading_value,
                "change_price": change_price,
                "change_rate": change_rate,
                "source": "KIS_API", "source_endpoints": ("kis/price",),
                "data_available": True}

    def get_orderbook(self, symbol: str) -> dict:
        out = self._get("domestic_stock_orderbook", _ORDERBOOK_PATH,
                        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol})
        if not out:
            return {"symbol": symbol, "data_available": False, "source": "KIS_API", "source_endpoints": ()}
        return {"symbol": symbol,
                "ask_price": _int(out.get("askp1", out.get("ask_price", 0))),
                "bid_price": _int(out.get("bidp1", out.get("bid_price", 0))),
                "source": "KIS_API", "source_endpoints": ("kis/orderbook",),
                "data_available": True}

    def get_execution_strength(self, symbol: str) -> dict:
        out = self._get("domestic_stock_execution", _EXEC_PATH,
                        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol})
        if not out:
            return {"symbol": symbol, "data_available": False, "source": "KIS_API", "source_endpoints": ()}
        return {"symbol": symbol,
                "execution_strength": _float(out.get("execution_strength", out.get("exe_str", 0))),
                "volume": _int(out.get("volume", out.get("acml_vol", 0))),
                "source": "KIS_API", "source_endpoints": ("kis/execution",),
                "data_available": True}


def _int(val) -> int:
    try: return int(float(str(val)))
    except (TypeError, ValueError): return 0

def _float(val) -> float:
    try: return float(val)
    except (TypeError, ValueError): return 0.0
