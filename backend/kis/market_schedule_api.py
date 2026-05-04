"""KIS Market Schedule API — 휴장일조회, 장운영정보"""
from __future__ import annotations
from kis.transport import KisTransport, StubTransport


class MarketScheduleApi:
    def __init__(self, transport: KisTransport | StubTransport, base_url: str):
        self._transport = transport
        self._base_url = base_url

    def get_holidays(self) -> list[str]:
        resp = self._transport.get_json(
            "/uapi/domestic-stock/v1/quotations/chk-holiday"
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Holiday query failed: {resp.body}")
        output = resp.body.get("output", [])
        if isinstance(output, list):
            return [item["bass_dt"] for item in output if "bass_dt" in item]
        return []

    def get_market_status(self) -> dict:
        resp = self._transport.get_json(
            "/uapi/domestic-stock/v1/quotations/market-status"
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Market status query failed: {resp.body}")
        return resp.body.get("output", {})


def get_holidays(api: MarketScheduleApi) -> list[str]:
    return api.get_holidays()


def get_market_status(api: MarketScheduleApi) -> dict:
    return api.get_market_status()
