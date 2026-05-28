from __future__ import annotations

import pytest

from kis.auth_headers import build_kis_auth_headers, validate_prod_vps_alignment
from kis.credentials import KisCredentials
from datetime import datetime, timedelta, timezone

from kis.auth import KisToken
from kis.token_provider import KisTokenProvider, TokenIssueError
from kis.transport import StubTransport
from kis.ws_approval import WsApprovalKey


@pytest.fixture(autouse=True)
def _isolate_token_cache(monkeypatch):
    import kis.token_provider as token_provider_mod

    class _EmptyTokenCache:
        def __init__(self, *args, **kwargs):
            pass

        def load(self):
            return None

        def token_present(self, rec):
            return False

        def is_expired(self, rec):
            return False

        def kst_attempted_today(self, rec):
            return False

        def record_tokenp_attempt(self, *args, **kwargs):
            return None

    monkeypatch.setattr(token_provider_mod, "TokenCache", _EmptyTokenCache)


def _credentials() -> KisCredentials:
    return KisCredentials(
        app_key="PSAPPKEY1234567890ABCDEF",
        app_secret="PSSECRET1234567890ABCDEF1234567890ABCDEF12",
        base_url="https://openapi.koreainvestment.com:9443",
        account_no="44413716-01",
    )


def test_tokenp_path_and_body_alignment() -> None:
    stub = StubTransport(responses={"/oauth2/tokenP": {"access_token": "t", "token_type": "Bearer", "expires_in": 86400}})
    p = KisTokenProvider("APP", "SECRET", "https://openapi.koreainvestment.com:9443", transport=stub)

    p.issue_token()

    method, path, body = stub.calls[0]
    assert method == "POST"
    assert path == "/oauth2/tokenP"
    assert body["grant_type"] == "client_credentials"
    assert body["appkey"] == "APP"
    assert body["appsecret"] == "SECRET"
    assert "secretkey" not in body


def test_tokenp_headers_alignment() -> None:
    stub = StubTransport(responses={"/oauth2/tokenP": {"access_token": "t", "token_type": "Bearer", "expires_in": 86400}})
    p = KisTokenProvider("APP", "SECRET", "https://openapi.koreainvestment.com:9443", transport=stub)

    p.issue_token()

    h = stub.last_headers or {}
    assert h.get("Content-Type") == "application/json"
    assert h.get("Accept") == "text/plain"
    assert h.get("charset") == "UTF-8"
    assert h.get("User-Agent")


def test_ws_approval_path_and_body_alignment() -> None:
    c = _credentials()
    stub = StubTransport(responses={"/oauth2/Approval": {"rt_cd": "0", "output": {"approval_key": "k"}}})
    ws = WsApprovalKey(credentials=c, transport=stub)

    ws.issue()

    method, path, body = stub.calls[0]
    assert method == "POST"
    assert path == "/oauth2/Approval"
    assert body["grant_type"] == "client_credentials"
    assert body["appkey"] == c.app_key
    assert body["secretkey"] == c.app_secret
    assert "appsecret" not in body


def test_ws_approval_headers_alignment() -> None:
    c = _credentials()
    stub = StubTransport(responses={"/oauth2/Approval": {"rt_cd": "0", "output": {"approval_key": "k"}}})
    ws = WsApprovalKey(credentials=c, transport=stub)

    ws.issue()

    h = stub.last_headers or {}
    assert h.get("Content-Type") == "application/json"
    assert h.get("Accept") == "text/plain"
    assert h.get("charset") == "UTF-8"
    assert h.get("User-Agent")


def test_token_403_classified_as_forbidden_and_sanitized() -> None:
    stub = StubTransport(responses={"/oauth2/tokenP": {"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "forbidden"}})
    p = KisTokenProvider("APP-SECRET-LEAK", "SECRET-LEAK", "https://openapi.koreainvestment.com:9443", transport=stub)

    # force 403 via custom response status with tiny monkey patch
    stub._responses["/oauth2/tokenP"] = {"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "forbidden"}
    original_post = stub.post_json

    def _post(path, json_data=None, headers=None):
        r = original_post(path, json_data=json_data, headers=headers)
        r = type(r)(status_code=403, body=r.body, headers=r.headers)
        return r

    stub.post_json = _post  # type: ignore[assignment]

    try:
        p.issue_token()
        assert False, "expected TokenIssueError"
    except TokenIssueError as e:
        msg = str(e)
        assert "KIS_TOKEN_FORBIDDEN" in msg
        assert "APP-SECRET-LEAK" not in msg
        assert "SECRET-LEAK" not in msg

    d = p.get_last_diagnostic()
    assert d is not None
    assert d.error_type == "KIS_TOKEN_FORBIDDEN"
    assert d.status_code == 403
    assert "PROD_VPS_MISMATCH" in d.possible_causes
    assert "IP_WHITELIST_NOT_REGISTERED" in d.possible_causes
    assert "APP_PERMISSION_DENIED" in d.possible_causes
    assert "ACCOUNT_PRODUCT_MISMATCH" in d.possible_causes
    assert d.domain_mode == "prod"
    assert d.expected_base_url == "https://openapi.koreainvestment.com:9443"


def test_token_403_error_code_fallback_to_msg_fields() -> None:
    stub = StubTransport(
        responses={
            "/oauth2/tokenP": {
                "error_code": "EGW00133",
                "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
            }
        }
    )
    p = KisTokenProvider("APP", "SECRET", "https://openapi.koreainvestment.com:9443", transport=stub)

    original_post = stub.post_json

    def _post(path, json_data=None, headers=None):
        r = original_post(path, json_data=json_data, headers=headers)
        return type(r)(status_code=403, body=r.body, headers=r.headers)

    stub.post_json = _post  # type: ignore[assignment]

    with pytest.raises(TokenIssueError) as exc:
        p.issue_token()

    assert "msg_cd=EGW00133" in str(exc.value)
    d = p.get_last_diagnostic()
    assert d is not None
    assert d.msg_cd == "EGW00133"
    assert "1분당 1회" in d.msg1


def test_token_cache_reduces_reissue_calls() -> None:
    stub = StubTransport(responses={"/oauth2/tokenP": {"access_token": "cached", "token_type": "Bearer", "expires_in": 86400}})
    p = KisTokenProvider("APP", "SECRET", "https://openapi.koreainvestment.com:9443", transport=stub)

    t1 = p.issue_token()
    t2 = p.issue_token()

    assert t1.access_token == "cached"
    assert t2.access_token == "cached"
    assert len(stub.calls) == 1


def test_token_cache_reissues_when_expired() -> None:
    stub = StubTransport(responses={"/oauth2/tokenP": {"access_token": "refreshed", "token_type": "Bearer", "expires_in": 86400}})
    p = KisTokenProvider("APP", "SECRET", "https://openapi.koreainvestment.com:9443", transport=stub)

    p._cached_token = KisToken(
        access_token="expired",
        token_type="Bearer",
        expires_in=1,
        issued_at=datetime.now(timezone.utc) - timedelta(seconds=120),
    )

    t = p.issue_token()
    assert t.access_token == "refreshed"
    assert len(stub.calls) == 1


def test_domain_alignment_helper_prod_vps() -> None:
    prod = validate_prod_vps_alignment("https://openapi.koreainvestment.com:9443", mode="prod")
    assert prod.is_match is True

    mismatch = validate_prod_vps_alignment("https://openapi.koreainvestment.com:9443", mode="vps")
    assert mismatch.is_match is False
    assert mismatch.warning_code == "PROD_VPS_MISMATCH"


def test_official_auth_header_builder() -> None:
    h = build_kis_auth_headers(user_agent="SAT3/3.0-test")
    assert h["Content-Type"] == "application/json"
    assert h["Accept"] == "text/plain"
    assert h["charset"] == "UTF-8"
    assert h["User-Agent"] == "SAT3/3.0-test"
