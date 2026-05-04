"""Tests for backend/kis/ws_approval.py — WebSocket approval key management."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from kis.ws_approval import (
    WsApprovalKey,
    ApprovalResponse,
    ApproveRequestBuilder,
    ApprovalKeyError,
    MASKED_APPROVAL_KEY,
)
from kis.credentials import KisCredentials
from kis.transport import StubTransport, TransportResponse


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def credentials():
    return KisCredentials(
        app_key="PSAPPKEY1234567890ABCDEF",
        app_secret="PSSECRET1234567890ABCDEF1234567890ABCDEF12",
        base_url="https://openapi.koreainvestment.com:9443",
        account_no="44413716-01",
    )


@pytest.fixture
def valid_response_dict():
    """KIS /oauth2/Approval 성공 응답 (dict)."""
    return {
        "rt_cd": "0",
        "msg_cd": "MCA00000",
        "msg1": "정상처리되었습니다",
        "output": {
            "approval_key": "real-approval-key-abcdef123456",
        },
    }


@pytest.fixture
def error_response_dict():
    """KIS approval error 응답 (dict)."""
    return {
        "rt_cd": "1",
        "msg_cd": "EGW00123",
        "msg1": "인증에 실패하였습니다",
    }


# ── ApproveRequestBuilder ────────────────────────────────────────────────────

class TestApproveRequestBuilder:
    def test_build_request(self, credentials):
        req = ApproveRequestBuilder.build(credentials)
        assert req["grant_type"] == "client_credentials"
        assert req["appkey"] == credentials.app_key
        assert req["secretkey"] == credentials.app_secret

    def test_does_not_include_account_no(self, credentials):
        req = ApproveRequestBuilder.build(credentials)
        assert "account_no" not in req


# ── ApprovalResponse ─────────────────────────────────────────────────────────

class TestApprovalResponse:
    def test_parse_success(self, valid_response_dict):
        resp = ApprovalResponse.parse(valid_response_dict)
        assert resp.success is True
        assert resp.approval_key == "real-approval-key-abcdef123456"
        assert resp.msg1 == "정상처리되었습니다"
        assert resp.rt_cd == "0"

    def test_parse_error(self, error_response_dict):
        resp = ApprovalResponse.parse(error_response_dict)
        assert resp.success is False
        assert resp.approval_key is None

    def test_parse_missing_output(self):
        resp = ApprovalResponse.parse({"rt_cd": "0"})
        assert resp.success is True
        assert resp.approval_key is None

    def test_parse_empty_output(self):
        resp = ApprovalResponse.parse({"rt_cd": "0", "output": {}})
        assert resp.success is True
        assert resp.approval_key is None


# ── WsApprovalKey with StubTransport ─────────────────────────────────────────

class TestWsApprovalKeyWithStubTransport:
    def test_issue_success(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        result = approval.issue()
        assert result == "real-approval-key-abcdef123456"
        assert approval._approval_key == "real-approval-key-abcdef123456"

    def test_issue_failure_raises(self, credentials, error_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": error_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        with pytest.raises(ApprovalKeyError):
            approval.issue()

    def test_masked_str(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        masked = str(approval)
        assert masked == MASKED_APPROVAL_KEY
        assert "real-approval-key" not in masked

    def test_repr_does_not_leak_key(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        r = repr(approval)
        assert "real-approval-key" not in r
        assert MASKED_APPROVAL_KEY in r

    def test_get_masked(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        masked = approval.get_masked()
        assert masked == MASKED_APPROVAL_KEY

    def test_issue_before_called_returns_none(self, credentials):
        stub = StubTransport(responses={})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        assert approval._approval_key is None

    def test_get_approval_key_returns_real_value(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        key = approval.get_approval_key()
        assert key == "real-approval-key-abcdef123456"


# ── Secret leak prevention ───────────────────────────────────────────────────

class TestSecretLeakPrevention:
    def test_app_key_not_in_masked_repr(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        r = repr(approval)
        assert credentials.app_key not in r
        assert credentials.app_secret not in r
        assert credentials.account_no not in r

    def test_app_key_not_in_masked_str(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        s = str(approval)
        assert credentials.app_key not in s
        assert credentials.app_secret not in s
        assert credentials.account_no not in s

    def test_masked_constant_format(self):
        assert MASKED_APPROVAL_KEY == "****-****-****"


# ── Transport interaction ────────────────────────────────────────────────────

class TestTransportInteraction:
    def test_calls_correct_endpoint(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        assert len(stub.calls) == 1
        method, path, json_data = stub.calls[0]
        assert method == "POST"
        assert path == "/oauth2/Approval"

    def test_passes_appkey_in_body(self, credentials, valid_response_dict):
        stub = StubTransport(responses={"/oauth2/Approval": valid_response_dict})
        approval = WsApprovalKey(credentials=credentials, transport=stub)
        approval.issue()
        _, _, json_data = stub.calls[0]
        assert json_data["appkey"] == credentials.app_key
        assert json_data["secretkey"] == credentials.app_secret
