from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kis.token_cache import TokenCache, TokenCacheRecord, app_key_fingerprint, base_url_hash
from kis.token_provider import KisTokenProvider


class NoNetworkTransport:
    def post_json(self, *args, **kwargs):
        raise AssertionError("network must not be called when cache is valid")

    def get_json(self, *args, **kwargs):
        raise AssertionError("network must not be called when cache is valid")


def test_cached_token_reconstruction_preserves_absolute_expiry(tmp_path, monkeypatch):
    cache_path = tmp_path / "kis_token_cache.json"
    monkeypatch.setenv("SAT3_KIS_TOKEN_CACHE_PATH", str(cache_path))

    now = datetime.now(timezone.utc)
    issued_at = now - timedelta(hours=1)
    expires_at = now + timedelta(hours=2)
    rec = TokenCacheRecord(
        access_token="cached-token",
        token_type="Bearer",
        issued_at_epoch=int(issued_at.timestamp()),
        expires_at_epoch=int(expires_at.timestamp()),
        issued_at_kst=issued_at.astimezone(timezone(timedelta(hours=9))).isoformat(),
        expires_at_kst=expires_at.astimezone(timezone(timedelta(hours=9))).isoformat(),
        source="KIS_TOKENP",
        base_url_hash=base_url_hash("https://openapi.koreainvestment.com:9443"),
        app_key_fingerprint=app_key_fingerprint("A" * 36),
    )
    TokenCache(cache_path).save(rec)

    provider = KisTokenProvider(
        app_key="A" * 36,
        app_secret="B" * 180,
        base_url="https://openapi.koreainvestment.com:9443",
        transport=NoNetworkTransport(),
    )

    token = provider.issue_token(force_token_refresh=False)

    assert token.access_token == "cached-token"
    assert token.token_type == "Bearer"
    assert token.is_expired is False
    assert int(token.expires_at.timestamp()) == int(expires_at.timestamp())
    assert int(token.expires_in) == int(expires_at.timestamp() - issued_at.timestamp())
