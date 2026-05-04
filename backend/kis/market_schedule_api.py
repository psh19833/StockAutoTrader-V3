"""KIS Market Schedule API — 휴장일조회, 장운영정보

실제 KIS 응답 구조: rt_cd + output 계열
"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class MarketScheduleApi:
    def __init__(self, transport: KisTransport | StubTransport, base_url: str):
        self._transport = transport
        self._base_url = base_url

    def _get_output(self, body: dict) -> dict | list:
        """output, output1, output2 중 첫 번째 존재하는 것 반환"""
        for key in ("output", "output1", "output2"):
            if key in body and body[key] is not None:
                return body[key]
        return {}

    def get_holidays(self) -> list[str]:
        resp = self._transport.get_json(
            "/uapi/domestic-stock/v1/quotations/chk-holiday"
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Holiday query failed: {resp.body}")
        output = self._get_output(resp.body)
        if isinstance(output, list):
            return [item["bass_dt"] for item in output if isinstance(item, dict) and "bass_dt" in item]
        if isinstance(output, dict) and "bass_dt" in output:
            return [output["bass_dt"]]
        return []

    def get_market_status(self) -> dict:
        resp = self._transport.get_json(
            "/uapi/domestic-stock/v1/quotations/market-status"
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Market status query failed: {resp.body}")
        output = self._get_output(resp.body)
        if isinstance(output, dict):
            status = output.get("market_status") or output.get("stck_mrkt_cls_cd") or output.get("mrkt_cls_cd", "")
            return {"market_status": str(status), "_raw_keys": list(output.keys())}
        return {"market_status": "unknown"}


def get_holidays(api: MarketScheduleApi) -> list[str]:
    return api.get_holidays()


def get_market_status(api: MarketScheduleApi) -> dict:
    return api.get_market_status()
