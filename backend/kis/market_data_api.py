"""KIS Market Data API — 현재가, 호가, 체결강도"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport

_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
_ORDERBOOK_PATH = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
_EXEC_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-ccnl"
_VOLUME_TOP_PATH = "/uapi/domestic-stock/v1/quotations/volume-rank"
_VOLUME_TOP_DEFAULT_PARAMS = {
    "FID_COND_MRKT_DIV_CODE": "J",
    "FID_COND_SCR_DIV_CODE": "20171",
    "FID_INPUT_ISCD": "0000",
    "FID_DIV_CLS_CODE": "0",
    "FID_BLNG_CLS_CODE": "0",
    "FID_TRGT_CLS_CODE": "111111111",
    "FID_TRGT_EXLS_CLS_CODE": "0000000000",
    "FID_INPUT_PRICE_1": "",
    "FID_INPUT_PRICE_2": "",
    "FID_VOL_CNT": "",
    "FID_INPUT_DATE_1": "",
}


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

    def get_volume_top(self, params: dict | None = None) -> dict:
        """거래량 순위 조회 (read-only).

        endpoint: inquire_trading_volume

        NOTE:
        - KIS volume-rank endpoint returns a list under `output`.
        - We return the raw payload so upstream parsers can extract symbols safely.
        - Failure responses include http_status/rt_cd/msg_cd/msg1 for observability.
        """
        request_params = dict(_VOLUME_TOP_DEFAULT_PARAMS)
        for key, value in (params or {}).items():
            if value is not None:
                request_params[key] = value

        if self._client:
            resp = self._client.get_json("inquire_trading_volume", params=request_params)
        elif self._transport:
            resp = self._transport.get_json(_VOLUME_TOP_PATH, params=request_params)
        else:
            return {"data_available": False, "source": "KIS_API", "source_endpoints": ("kis/volume_top",)}

        body = resp.body if isinstance(resp.body, dict) else {}
        rt_cd = str(body.get("rt_cd", ""))
        msg_cd = str(body.get("msg_cd", ""))
        msg1 = str(body.get("msg1", ""))

        if resp.status_code != 200:
            return {
                "data_available": False,
                "source": "KIS_API",
                "source_endpoints": ("kis/volume_top",),
                "http_status": resp.status_code,
                "rt_cd": rt_cd,
                "msg_cd": msg_cd,
                "msg1": msg1,
                "error_type": "KIS_HTTP_ERROR",
                "reason_code": msg_cd or "KIS_HTTP_ERROR",
                "reason_text": msg1 or "KIS volume-top request failed",
            }

        if not body or rt_cd not in ("", "0"):
            return {
                "data_available": False,
                "source": "KIS_API",
                "source_endpoints": ("kis/volume_top",),
                "http_status": resp.status_code,
                "rt_cd": rt_cd,
                "msg_cd": msg_cd,
                "msg1": msg1,
                "error_type": "KIS_API_ERROR",
                "reason_code": msg_cd or body.get("reason_code") or "KIS_API_ERROR",
                "reason_text": msg1 or body.get("reason_text") or "KIS volume-top returned an error",
            }

        return {
            "data_available": True,
            "source": "KIS_API",
            "source_endpoints": ("kis/volume_top",),
            "raw": body,
            "http_status": resp.status_code,
            "rt_cd": rt_cd,
            "msg_cd": msg_cd,
            "msg1": msg1,
        }


def _int(val) -> int:
    try: return int(float(str(val)))
    except (TypeError, ValueError): return 0

def _float(val) -> float:
    try: return float(val)
    except (TypeError, ValueError): return 0.0
