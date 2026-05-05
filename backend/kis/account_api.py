"""KIS Account API — 잔고조회, 체결조회 (주문 제출 금지)"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport

_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
_FILLS_PATH = "/uapi/domestic-stock/v1/trading/inquire-ccnl"
class AccountApi:
    def __init__(
        self,
        transport: KisTransport | None = None,
        base_url: str | None = None,
        client: KisClient | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
    ):
        self._transport = transport
        self._base_url = base_url
        self._client = client
        self._account_no = account_no
        self._account_product_code = account_product_code

    def _get_account_parts(self) -> tuple[str, str]:
        """Return (CANO, ACNT_PRDT_CD). Supports env fallback.

        Accepts either:
        - account_no like "44413716" and product_code like "01"
        - or account_no like "44413716-01" (product inferred if not separately provided)
        """
        import os

        raw_no = (self._account_no or os.getenv("KIS_ACCOUNT_NO") or "").strip()

        # If account_no already includes product code (e.g. "44413716-01"),
        # treat it as authoritative and DO NOT let env override parsing.
        if raw_no and "-" in raw_no:
            raw_prdt = (self._account_product_code or "").strip()
        else:
            raw_prdt = (self._account_product_code or os.getenv("KIS_ACCOUNT_PRODUCT_CODE") or "").strip()

        cano = ""
        prdt = ""
        if raw_no and "-" in raw_no and not raw_prdt:
            left, right = raw_no.split("-", 1)
            cano = left.strip()
            prdt = right.strip()
        else:
            cano = raw_no
            prdt = raw_prdt

        # Normalize digits only (defensive). Keep length expectations (8 / 2).
        cano = "".join(ch for ch in cano if ch.isdigit())
        prdt = "".join(ch for ch in prdt if ch.isdigit())

        if len(cano) != 8 or len(prdt) != 2:
            raise ValueError("KIS account info not configured")
        return cano, prdt

    def _get(self, endpoint_name: str, fallback_path: str, params: dict | None = None) -> dict:
        if self._client:
            resp = self._client.get_json(endpoint_name, params=params)
        elif self._transport:
            resp = self._transport.get_json(fallback_path, params=params)
        else:
            return {}
        if resp.status_code != 200:
            return {}
        return resp.body

    def get_balance(self) -> dict:
        try:
            cano, prdt = self._get_account_parts()
        except ValueError:
            # If account params are not configured, do not call KIS.
            return {"positions": [], "data_available": False}

        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        body = self._get("inquire_balance", _BALANCE_PATH, params=params)
        if not body:
            return {"positions": [], "data_available": False}
        output = body.get("output", [])
        positions = []
        if isinstance(output, list):
            for item in output:
                positions.append({"symbol": item.get("pdno", ""),
                                  "quantity": _int(item.get("hldg_qty", 0)),
                                  "avg_buy_price": _int(item.get("pchs_avg_pric", 0)),
                                  "current_price": _int(item.get("prpr", 0))})
        return {"positions": positions, "total_buyable": _int(body.get("total_buyable", 0)),
                "source": "KIS_API", "source_endpoints": ("kis/balance",), "data_available": True}

    def get_fills(
        self,
        inqr_strt_dt: str | None = None,
        inqr_end_dt: str | None = None,
        pdno: str = "",
    ) -> list[dict]:
        from datetime import datetime

        try:
            cano, prdt = self._get_account_parts()
        except ValueError:
            # If account params are not configured, do not call KIS.
            return []

        today = datetime.now().strftime("%Y%m%d")
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "INQR_STRT_DT": (inqr_strt_dt or today),
            "INQR_END_DT": (inqr_end_dt or today),
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": pdno,
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        body = self._get("inquire_ccnl", _FILLS_PATH, params=params)
        if not body:
            return []
        output = body.get("output", [])
        fills = []
        if isinstance(output, list):
            for item in output:
                fills.append({"order_id": item.get("odno", ""), "symbol": item.get("pdno", ""),
                              "side": "BUY" if item.get("sll_buy_dvsn_cd") == "02" else "SELL",
                              "filled_qty": _int(item.get("tot_ccld_qty", 0)),
                              "filled_amount": _int(item.get("tot_ccld_amt", 0)),
                              "remaining_qty": _int(item.get("rmn_qty", 0)),
                              "source": "KIS_API", "source_endpoints": ("kis/fills",)})
        return fills


def _int(val) -> int:
    try: return int(val)
    except (TypeError, ValueError): return 0
