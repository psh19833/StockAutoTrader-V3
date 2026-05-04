"""KisTokenProvider — KIS OAuth 토큰 발급/갱신

transport 주입 방식으로 테스트 가능.
token 원문을 repr/log에 노출하지 않는다.
"""
from __future__ import annotations
from datetime import datetime, timezone

from kis.auth import KisToken
from kis.transport import KisTransport, StubTransport


class TokenIssueError(Exception):
    pass


class KisTokenProvider:
    def __init__(self, app_key: str, app_secret: str, base_url: str,
                 transport: KisTransport | StubTransport | None = None):
        self._app_key = app_key
        self._app_secret = app_secret
        self._base_url = base_url
        self._transport = transport

    def issue_token(self) -> KisToken:
        if self._transport is None:
            raise RuntimeError("No transport configured")
        resp = self._transport.post_json(
            "/oauth2/tokenP",
            json_data={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "appsecret": self._app_secret,
            },
        )
        if resp.status_code != 200 or "access_token" not in resp.body:
            raise TokenIssueError(
                f"Token issue failed: {resp.body.get('error', 'unknown')}"
            )
        return KisToken(
            access_token=resp.body["access_token"],
            token_type=resp.body.get("token_type", "Bearer"),
            expires_in=resp.body.get("expires_in", 86400),
            issued_at=datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return f"KisTokenProvider(app_key=****, base_url={self._base_url})"
