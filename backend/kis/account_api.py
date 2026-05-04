"""KIS Account API — 잔고조회, 체결조회 (주문 제출 금지)"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class AccountApi:
    def __init__(self, transport: KisTransport | StubTransport, base_url: str):
        self._transport = transport
        self._base_url = base_url

    def get_balance(self) -> dict:
        resp = self._transport.get_json("/uapi/balance")
        if resp.status_code != 200:
            return {"positions": [], "data_available": False}
        output = resp.body.get("output", [])
        positions = []
        if isinstance(output, list):
            for item in output:
                positions.append({
                    "symbol": item.get("pdno", ""),
                    "quantity": _int(item.get("hldg_qty", 0)),
                    "avg_buy_price": _int(item.get("pchs_avg_pric", 0)),
                    "current_price": _int(item.get("prpr", 0)),
                })
        return {
            "positions": positions,
            "total_buyable": _int(resp.body.get("total_buyable", 0)),
            "source": "KIS_API",
            "source_endpoints": ("kis/balance",),
            "data_available": True,
        }

    def get_fills(self) -> list[dict]:
        resp = self._transport.get_json("/uapi/fills")
        if resp.status_code != 200:
            return []
        output = resp.body.get("output", [])
        fills = []
        if isinstance(output, list):
            for item in output:
                fills.append({
                    "order_id": item.get("odno", ""),
                    "symbol": item.get("pdno", ""),
                    "side": "BUY" if item.get("sll_buy_dvsn_cd") == "02" else "SELL",
                    "filled_qty": _int(item.get("tot_ccld_qty", 0)),
                    "filled_amount": _int(item.get("tot_ccld_amt", 0)),
                    "remaining_qty": _int(item.get("rmn_qty", 0)),
                    "source": "KIS_API",
                    "source_endpoints": ("kis/fills",),
                })
        return fills


def _int(val) -> int:
    try: return int(val)
    except (TypeError, ValueError): return 0
