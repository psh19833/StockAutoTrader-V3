from __future__ import annotations

import json
import urllib.error

import pytest


def test_realtransport_get_params_appends_query(monkeypatch):
    from kis.transport import RealTransport

    captured = {}

    class DummyResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        return DummyResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    t = RealTransport(base_url="https://example.com", timeout=1)
    t.get_json("/uapi/domestic-stock/v1/quotations/inquire-price", params={"FID_INPUT_ISCD": "005930"})

    assert "FID_INPUT_ISCD=005930" in captured["url"]


def test_realtransport_get_params_appends_with_ampersand_when_query_exists(monkeypatch):
    from kis.transport import RealTransport

    captured = {}

    class DummyResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        return DummyResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    t = RealTransport(base_url="https://example.com", timeout=1)
    t.get_json("/path?existing=1", params={"a": "b"})
    assert captured["url"].endswith("/path?existing=1&a=b")


def test_realtransport_get_params_none_keeps_url(monkeypatch):
    from kis.transport import RealTransport

    captured = {}

    class DummyResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        return DummyResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    t = RealTransport(base_url="https://example.com", timeout=1)
    t.get_json("/path", params=None)
    assert captured["url"] == "https://example.com/path"


def test_realtransport_blocks_order_endpoint_even_with_full_url_and_query():
    from kis.transport import RealTransport
    from kis.errors import OrderEndpointBlockedError

    t = RealTransport(base_url="https://example.com", timeout=1)
    with pytest.raises(OrderEndpointBlockedError):
        t.get_json("https://example.com/uapi/domestic-stock/v1/trading/order-cash?x=1")


def test_kisclient_blocks_order_endpoint_even_with_full_url_and_query():
    from kis.client import KisClient
    from kis.transport import StubTransport
    from kis.errors import OrderEndpointBlockedError

    c = KisClient(base_url="https://example.com", transport=StubTransport(), app_key="k", app_secret="s")
    with pytest.raises(OrderEndpointBlockedError):
        c.get_json("https://example.com/uapi/domestic-stock/v1/trading/order-credit?x=1")


def test_transport_protocol_accepts_headers_via_fake_transport():
    from kis.client import KisClient

    class FakeTransport:
        def __init__(self):
            self.last = None

        def get_json(self, path: str, params=None, headers=None):
            self.last = (path, params, headers)
            from kis.transport import TransportResponse

            return TransportResponse(200, {})

        def post_json(self, path: str, json_data=None, headers=None):
            self.last = (path, json_data, headers)
            from kis.transport import TransportResponse

            return TransportResponse(200, {})

    ft = FakeTransport()
    c = KisClient(base_url="https://example.com", transport=ft, app_key="k", app_secret="s")
    c.get_json("/some/path")
    assert ft.last is not None
    assert isinstance(ft.last[2], dict)


def test_ws_approval_parse_supports_output_and_top_level():
    from kis.ws_approval import ApprovalResponse

    b1 = {"rt_cd": "0", "output": {"approval_key": "ABC"}}
    r1 = ApprovalResponse.parse(b1)
    assert r1.success is True
    assert r1.approval_key == "ABC"

    b2 = {"approval_key": "TOP"}
    r2 = ApprovalResponse.parse(b2)
    assert r2.success is True
    assert r2.approval_key == "TOP"

    b3 = {"rt_cd": "1", "approval_key": "SHOULD_NOT"}
    r3 = ApprovalResponse.parse(b3)
    assert r3.success is False
    assert r3.approval_key is None


def test_endpoints_realtime_websocket_approval_path():
    from kis.endpoints import get_endpoint

    ep = get_endpoint("realtime_websocket")
    assert ep.path == "/oauth2/Approval"

    ep2 = get_endpoint("websocket_approval")
    assert ep2.path == "/oauth2/Approval"


def test_ws_receive_once_parses_and_does_not_store_raw(monkeypatch):
    from kis.ws_client import GuardedRealWebSocketClient, ConnectionState

    class FakeWs:
        def __init__(self, raw):
            self._raw = raw

        def recv(self):
            return self._raw

    raw = json.dumps({"tr_id": "H0STCNT0", "MKSC_SHRN_ISCD": "005930", "STCK_PRPR": "70000", "CNTG_VOL": "1", "STCK_CNTG_HOUR": "090000"})

    c = GuardedRealWebSocketClient()
    c._ws = FakeWs(raw)
    c._connection_state = ConnectionState.CONNECTED

    parsed = c.receive_once()
    assert getattr(parsed, "parsed_ok", None) is True
    assert getattr(c, "_last_raw_hash", None)

    # Ensure raw is not stored verbatim anywhere obvious
    assert not hasattr(c, "_last_raw")


def test_ws_receive_once_invalid_message_returns_parsed_ok_false(monkeypatch):
    from kis.ws_client import GuardedRealWebSocketClient, ConnectionState

    class FakeWs:
        def recv(self):
            return "not a json"

    c = GuardedRealWebSocketClient()
    c._ws = FakeWs()
    c._connection_state = ConnectionState.CONNECTED

    parsed = c.receive_once()
    assert parsed.parsed_ok is False


def test_query_facade_exception_visibility_no_secret_leak():
    from kis.query_facade import KisQueryFacade

    f = KisQueryFacade(client=None)

    def boom():
        raise RuntimeError("access_token=SHOULD_NOT_LEAK")

    out = f._safe_call(boom)
    assert out["data_available"] is False
    assert out["error_type"] == "RuntimeError"
    assert out["reason_code"] == "KIS_QUERY_FAILED"
    assert "SHOULD_NOT_LEAK" not in json.dumps(out)


def test_realtransport_httperror_body_preserved_and_sanitized(monkeypatch):
    from kis.transport import RealTransport

    class DummyHTTPError(urllib.error.HTTPError):
        def __init__(self, url, code, msg, hdrs, fp, body_bytes: bytes):
            super().__init__(url, code, msg, hdrs, fp)
            self._body_bytes = body_bytes

        def read(self):
            return self._body_bytes

    def fake_urlopen(req, timeout=0):
        body = {
            "rt_cd": "1",
            "msg_cd": "ERR",
            "msg1": "bad",
            "access_token": "SHOULD_NOT_LEAK",
            "KIS_APP_SECRET": "SHOULD_NOT_LEAK",
        }
        raise DummyHTTPError(req.full_url, 403, "Forbidden access_token=SHOULD_NOT_LEAK", None, None, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    t = RealTransport(base_url="https://example.com", timeout=1)
    resp = t.get_json("/some/path")
    assert resp.status_code == 403
    assert resp.body.get("rt_cd") == "1"
    assert resp.body.get("msg_cd") == "ERR"
    assert resp.body.get("msg1") == "bad"

    dumped = json.dumps(resp.body)
    assert "SHOULD_NOT_LEAK" not in dumped
    assert "access_token" not in dumped
    assert "KIS_APP_SECRET" not in dumped


def test_kis_readonly_smoke_has_no_placeholder_paths():
    import pathlib

    p = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "kis_readonly_smoke.py"
    txt = p.read_text(encoding="utf-8")
    assert "/uapi/price" not in txt
    assert "/uapi/stock-info" not in txt


def test_market_data_and_stock_info_transport_fallback_passes_params():
    from kis.market_data_api import MarketDataApi
    from kis.stock_info_api import StockInfoApi
    from kis.transport import StubTransport

    st = StubTransport(responses={
        "/uapi/domestic-stock/v1/quotations/inquire-price": {"output": {"stck_prpr": "1"}},
        "/uapi/domestic-stock/v1/quotations/inquire-stock-basic": {"output": {"prdt_type_cd": "01", "mrkt_ctg": "KOSPI"}},
    })

    m = MarketDataApi(transport=st)
    m.get_current_price("005930")
    assert st.calls[-1][0] == "GET"
    assert st.calls[-1][2] is not None
    assert st.calls[-1][2].get("FID_INPUT_ISCD") == "005930"

    s = StockInfoApi(transport=st)
    s.get_stock_info("005930")
    assert st.calls[-1][2] is not None
    assert st.calls[-1][2].get("FID_INPUT_ISCD") == "005930"


def test_account_api_builds_required_params_for_balance_and_fills(monkeypatch):
    from kis.account_api import AccountApi
    from kis.transport import StubTransport

    st = StubTransport(responses={
        "/uapi/domestic-stock/v1/trading/inquire-balance": {"output": []},
        "/uapi/domestic-stock/v1/trading/inquire-ccnl": {"output": []},
    })

    api = AccountApi(transport=st, account_no="44413716-01")

    api.get_balance()
    assert st.calls, "expected transport to be called when account_no is provided"
    method, path, params = st.calls[-1]
    assert path == "/uapi/domestic-stock/v1/trading/inquire-balance"
    assert params["CANO"] == "44413716"
    assert params["ACNT_PRDT_CD"] == "01"

    api.get_fills(inqr_strt_dt="20250101", inqr_end_dt="20250101")
    method, path, params = st.calls[-1]
    assert path == "/uapi/domestic-stock/v1/trading/inquire-ccnl"
    assert params["CANO"] == "44413716"
    assert params["ACNT_PRDT_CD"] == "01"
    assert params["INQR_STRT_DT"] == "20250101"
    assert params["INQR_END_DT"] == "20250101"
