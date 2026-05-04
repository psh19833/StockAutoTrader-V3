"""Tests for N4-A: KIS Credentials, Transport, Token Provider"""
from __future__ import annotations

import pytest
from kis.credentials import KisCredentials
from kis.transport import KisTransport, StubTransport, TransportResponse
from kis.token_provider import KisTokenProvider


class TestKisCredentials:
    def test_create(self):
        creds = KisCredentials(
            app_key="test_key", app_secret="test_secret",
            base_url="https://openapi.koreainvestment.com:9443",
        )
        assert creds.app_key == "test_key"

    def test_masked_dict_hides_secrets(self):
        creds = KisCredentials(
            app_key="PSH1234567890", app_secret="my_secret_value_abc",
            base_url="https://test.com", account_no="44413716-01",
        )
        d = creds.masked_dict()
        assert d["app_key"] != "PSH1234567890"
        assert d["app_secret"] != "my_secret_value_abc"
        assert d["account_no"] != "44413716-01"
        assert "****" in str(d["app_secret"])

    def test_repr_no_secret(self):
        creds = KisCredentials(
            app_key="PSH1234567890", app_secret="my_secret_value_abc",
            base_url="https://test.com",
        )
        r = repr(creds)
        assert "PSH1234567890" not in r
        assert "my_secret_value_abc" not in r

    def test_validate_required_passes(self):
        creds = KisCredentials(
            app_key="test", app_secret="test",
            base_url="https://test.com",
        )
        result = creds.validate_required()
        assert result is True

    def test_validate_required_missing_app_key(self):
        creds = KisCredentials(app_key="", app_secret="test",
                               base_url="https://test.com")
        with pytest.raises(ValueError):
            creds.validate_required()

    def test_account_no_optional(self):
        creds = KisCredentials(
            app_key="test", app_secret="test", base_url="https://test.com",
        )
        assert creds.account_no is None

    def test_from_env_missing(self):
        creds = KisCredentials.from_env(env_prefix="NOT_SET_")
        assert creds.app_key == ""


class TestStubTransport:
    def test_get_json(self):
        transport = StubTransport(responses={"/test": {"key": "value"}})
        resp = transport.get_json("/test")
        assert resp.status_code == 200
        assert resp.body == {"key": "value"}

    def test_post_json(self):
        transport = StubTransport(responses={"/token": {"access_token": "stub_token"}})
        resp = transport.post_json("/token", json_data={"grant_type": "client_credentials"})
        assert resp.status_code == 200
        assert resp.body["access_token"] == "stub_token"

    def test_missing_endpoint(self):
        transport = StubTransport(responses={})
        resp = transport.get_json("/unknown")
        assert resp.status_code == 404

    def test_transport_is_abstract(self):
        assert hasattr(KisTransport, 'get_json')
        assert hasattr(KisTransport, 'post_json')

    def test_no_http_in_test(self):
        """StubTransport uses no real HTTP"""
        transport = StubTransport()
        resp = transport.get_json("/test")
        # Response is default empty
        assert resp.status_code == 404


class TestKisTokenProvider:
    def test_issue_token_success(self):
        transport = StubTransport(responses={
            "/oauth2/tokenP": {
                "access_token": "fake_token_abc123",
                "token_type": "Bearer",
                "expires_in": 86400,
            }
        })
        provider = KisTokenProvider(
            app_key="test_key", app_secret="test_secret",
            base_url="https://test.com", transport=transport,
        )
        token = provider.issue_token()
        assert token.access_token == "fake_token_abc123"
        assert token.token_type == "Bearer"
        assert token.expires_in == 86400

    def test_issue_token_failure(self):
        transport = StubTransport(responses={
            "/oauth2/tokenP": {"error": "invalid_client"}
        })
        provider = KisTokenProvider(
            app_key="test_key", app_secret="test_secret",
            base_url="https://test.com", transport=transport,
        )
        with pytest.raises(Exception):
            provider.issue_token()

    def test_no_secret_in_repr(self):
        provider = KisTokenProvider(
            app_key="PSH1234567890", app_secret="my_secret",
            base_url="https://test.com",
        )
        r = repr(provider)
        assert "PSH1234567890" not in r
        assert "my_secret" not in r
