from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from kis.auth import KisToken
from kis.client import KisClient
from kis.market_data_api import MarketDataApi
from kis.transport import StubTransport
from runtime.universe_source import fetch_universe_from_kis_volume_top


@dataclass
class _FakeFacadeError:
    payload: dict

    def get_volume_top(self, params=None):
        return self.payload


def _make_authed_client(transport: StubTransport) -> KisClient:
    client = KisClient(
        base_url="https://openapi.koreainvestment.com:9443",
        transport=transport,
        app_key="test-app-key",
        app_secret="test-app-secret",
    )
    client.auth_manager.set_token(
        KisToken(
            access_token="test-access-token",
            token_type="Bearer",
            expires_in=3600,
            issued_at=datetime.now(timezone.utc),
        )
    )
    return client


def test_volume_top_uses_official_path_and_defaults() -> None:
    transport = StubTransport(
        {
            "/uapi/domestic-stock/v1/quotations/volume-rank": {
                "rt_cd": "0",
                "msg_cd": "MCA00000",
                "msg1": "정상처리 되었습니다.",
                "output": [
                    {"mksc_shrn_iscd": "005930"},
                    {"mksc_shrn_iscd": "000660"},
                ],
            }
        }
    )
    api = MarketDataApi(client=_make_authed_client(transport))

    result = api.get_volume_top(params={})

    assert result["data_available"] is True
    assert result["raw"]["output"][0]["mksc_shrn_iscd"] == "005930"
    assert transport.call_details[-1]["method"] == "GET"
    assert transport.call_details[-1]["path"] == "/uapi/domestic-stock/v1/quotations/volume-rank"
    assert transport.call_details[-1]["payload"]["FID_COND_SCR_DIV_CODE"] == "20171"
    assert transport.call_details[-1]["payload"]["FID_INPUT_ISCD"] == "0000"


def test_volume_top_failure_propagates_reason_fields() -> None:
    transport = StubTransport(
        {
            "/uapi/domestic-stock/v1/quotations/volume-rank": {
                "rt_cd": "1",
                "msg_cd": "EGW00304",
                "msg1": "고객식별키(법인 personalSeckey, 개인 appSecret)가 유효하지 않습니다.",
            }
        }
    )
    api = MarketDataApi(client=_make_authed_client(transport))

    result = api.get_volume_top(params={})

    assert result["data_available"] is False
    assert result["http_status"] == 200
    assert result["rt_cd"] == "1"
    assert result["msg_cd"] == "EGW00304"
    assert result["reason_code"] == "EGW00304"
    assert "고객식별키" in result["reason_text"]


def test_universe_fetch_preserves_kis_failure_metadata() -> None:
    result = fetch_universe_from_kis_volume_top(
        _FakeFacadeError(
            {
                "data_available": False,
                "error_type": "KIS_API_ERROR",
                "reason_code": "EGW00304",
                "reason_text": "고객식별키 오류",
                "http_status": 200,
                "rt_cd": "1",
                "msg_cd": "EGW00304",
                "msg1": "고객식별키 오류",
            }
        ),
        top_n=10,
    )

    assert result.symbols == []
    assert result.error_type == "KIS_API_ERROR"
    assert result.error_reason == "EGW00304"
    assert result.http_status == 200
    assert result.rt_cd == "1"
    assert result.msg_cd == "EGW00304"
    assert result.msg1 == "고객식별키 오류"
