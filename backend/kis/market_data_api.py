"""KIS Market Data API — 현재가, 호가, 체결강도"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class MarketDataApi:
    def __init__(self, transport: KisTransport | StubTransport, base_url: str):
        self._transport = transport
        self._base_url = base_url

    def _safe_get(self, path: str, default: dict) -> dict:
        resp = self._transport.get_json(path)
        if resp.status_code == 200 and "output" in resp.body:
            return resp.body["output"]
        return default

    def get_current_price(self, symbol: str) -> dict:
        result = self._safe_get("/uapi/price", {})
        if not result:
            return {"symbol": symbol, "data_available": False,
                    "source": "KIS_API", "source_endpoints": ()}
        return {
            "symbol": symbol,
            "current_price": _int(result.get("stck_prpr", 0)),
            "open_price": _int(result.get("stck_oprc", 0)),
            "high_price": _int(result.get("stck_hgpr", 0)),
            "low_price": _int(result.get("stck_lwpr", 0)),
            "source": "KIS_API",
            "source_endpoints": ("kis/price",),
            "data_available": True,
        }

    def get_orderbook(self, symbol: str) -> dict:
        result = self._safe_get("/uapi/orderbook", {})
        if not result:
            return {"symbol": symbol, "data_available": False,
                    "source": "KIS_API", "source_endpoints": ()}
        return {
            "symbol": symbol,
            "ask_price": _int(result.get("ask_price", 0)),
            "bid_price": _int(result.get("bid_price", 0)),
            "source": "KIS_API",
            "source_endpoints": ("kis/orderbook",),
            "data_available": True,
        }

    def get_execution_strength(self, symbol: str) -> dict:
        result = self._safe_get("/uapi/execution", {})
        if not result:
            return {"symbol": symbol, "data_available": False,
                    "source": "KIS_API", "source_endpoints": ()}
        return {
            "symbol": symbol,
            "execution_strength": _float(result.get("execution_strength", 0)),
            "volume": _int(result.get("volume", 0)),
            "source": "KIS_API",
            "source_endpoints": ("kis/execution",),
            "data_available": True,
        }


def _int(val) -> int:
    try: return int(val)
    except (TypeError, ValueError): return 0

def _float(val) -> float:
    try: return float(val)
    except (TypeError, ValueError): return 0.0
