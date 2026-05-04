"""KIS Market Schedule API — 휴장일조회, 장운영정보"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class MarketScheduleApi:
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
        return resp.body if resp.status_code == 200 else {}

    def _get_output(self, body: dict):
        for key in ("output", "output1", "output2"):
            if key in body and body[key] is not None:
                return body[key]
        return {}

    def get_holidays(self) -> list[str]:
        body = self._get("/uapi/domestic-stock/v1/quotations/chk-holiday")
        if not body:
            return []
        output = self._get_output(body)
        if isinstance(output, list):
            return [item["bass_dt"] for item in output if isinstance(item, dict) and "bass_dt" in item]
        if isinstance(output, dict) and "bass_dt" in output:
            return [output["bass_dt"]]
        return []

    def get_market_status(self) -> dict:
        body = self._get("/uapi/domestic-stock/v1/quotations/market-status")
        if not body:
            return {"market_status": "unknown"}
        output = self._get_output(body)
        if isinstance(output, dict):
            status = output.get("market_status") or output.get("stck_mrkt_cls_cd", "unknown")
            return {"market_status": str(status)}
        return {"market_status": "unknown"}


def get_holidays(api: MarketScheduleApi) -> list[str]:
    return api.get_holidays()

def get_market_status(api: MarketScheduleApi) -> dict:
    return api.get_market_status()
