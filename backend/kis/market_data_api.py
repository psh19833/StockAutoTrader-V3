"""KIS Market Data API — 현재가, 호가, 체결강도"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class MarketDataApi:
    def __init__(self, transport=None, base_url: str = "", client=None):
        self._transport = transport
        self._base_url = base_url
        self._client = client

    def _get(self, path: str) -> dict:
        if self._client:
            resp = self._client.get_json(path)
        elif self._transport:
            resp = self._transport.get_json(path)
        else:
            return {}
        if resp.status_code != 200:
            return {}
        for key in ("output", "output1", "output2"):
            if key in resp.body and isinstance(resp.body[key], dict):
                return resp.body[key]
        return {}

    def get_current_price(self, symbol: str) -> dict:
        out = self._get("/uapi/price")
        if not out:
            return {"symbol": symbol, "data_available": False,
                    "source": "KIS_API", "source_endpoints": ()}
        price_keys = ("stck_prpr", "prpr", "current_price", "last_price")
        price = 0
        for k in price_keys:
            if k in out:
                price = _int(out[k])
                break
        return {
            "symbol": symbol, "current_price": price,
            "open_price": _int(out.get("stck_oprc", out.get("oprc", 0))),
            "high_price": _int(out.get("stck_hgpr", out.get("hgpr", 0))),
            "low_price": _int(out.get("stck_lwpr", out.get("lwpr", 0))),
            "source": "KIS_API", "source_endpoints": ("kis/price",),
            "data_available": True,
        }

    def get_orderbook(self, symbol: str) -> dict:
        out = self._get("/uapi/orderbook")
        if not out:
            return {"symbol": symbol, "data_available": False, "source": "KIS_API", "source_endpoints": ()}
        return {"symbol": symbol,
                "ask_price": _int(out.get("askp1", out.get("ask_price", 0))),
                "bid_price": _int(out.get("bidp1", out.get("bid_price", 0))),
                "source": "KIS_API", "source_endpoints": ("kis/orderbook",),
                "data_available": True}

    def get_execution_strength(self, symbol: str) -> dict:
        out = self._get("/uapi/execution")
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
