"""KisTokenProvider — KIS OAuth 토큰 발급/갱신

transport 주입 방식으로 테스트 가능.
token 원문을 repr/log에 노출하지 않는다.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from kis.auth import KisToken
from kis.auth_headers import build_kis_auth_headers, validate_prod_vps_alignment
from kis.transport import KisTransport, StubTransport


class TokenIssueError(Exception):
    pass


@dataclass(frozen=True)
class TokenIssueDiagnostic:
    error_type: str
    status_code: int
    possible_causes: list[str]
    rt_cd: str
    msg_cd: str
    msg1: str
    error_code: str = ""
    error_description: str = ""
    warning_code: str = ""
    domain_mode: str = ""
    expected_base_url: str = ""


class KisTokenProvider:
    def __init__(self, app_key: str, app_secret: str, base_url: str,
                 transport: KisTransport | StubTransport | None = None):
        self._app_key = app_key
        self._app_secret = app_secret
        self._base_url = base_url
        self._transport = transport
        self._cached_token: KisToken | None = None
        self._last_diagnostic: TokenIssueDiagnostic | None = None

    def _is_cached_token_valid(self) -> bool:
        return self._cached_token is not None and (not self._cached_token.is_expired)

    def get_last_diagnostic(self) -> TokenIssueDiagnostic | None:
        return self._last_diagnostic

    def issue_token(self) -> KisToken:
        if self._is_cached_token_valid():
            return self._cached_token  # type: ignore[return-value]

        if self._transport is None:
            raise RuntimeError("No transport configured")

        alignment = validate_prod_vps_alignment(self._base_url)
        headers = build_kis_auth_headers()

        resp = self._transport.post_json(
            "/oauth2/tokenP",
            json_data={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "appsecret": self._app_secret,
            },
            headers=headers,
        )
        if resp.status_code != 200 or "access_token" not in resp.body:
            rt_cd = str(resp.body.get("rt_cd", ""))
            msg_cd = str(resp.body.get("msg_cd", ""))
            msg1 = str(resp.body.get("msg1", ""))
            error_code = str(resp.body.get("error_code", ""))
            error_description = str(resp.body.get("error_description", ""))

            # Some KIS gateway responses return error_code/error_description instead of msg_cd/msg1.
            if not msg_cd and error_code:
                msg_cd = error_code
            if not msg1 and error_description:
                msg1 = error_description

            if resp.status_code == 403:
                self._last_diagnostic = TokenIssueDiagnostic(
                    error_type="KIS_TOKEN_FORBIDDEN",
                    status_code=403,
                    possible_causes=[
                        "IP_WHITELIST_NOT_REGISTERED",
                        "APP_PERMISSION_DENIED",
                        "PROD_VPS_MISMATCH",
                        "ACCOUNT_PRODUCT_MISMATCH",
                    ],
                    rt_cd=rt_cd,
                    msg_cd=msg_cd,
                    msg1=msg1,
                    error_code=error_code,
                    error_description=error_description,
                    warning_code=alignment.warning_code,
                    domain_mode=alignment.mode,
                    expected_base_url=alignment.expected_base_url,
                )
                raise TokenIssueError(
                    f"KIS_TOKEN_FORBIDDEN status=403 rt_cd={rt_cd} msg_cd={msg_cd} msg1={msg1} warning_code={alignment.warning_code} mode={alignment.mode}"
                )
            self._last_diagnostic = TokenIssueDiagnostic(
                error_type="KIS_TOKEN_ISSUE_FAILED",
                status_code=resp.status_code,
                possible_causes=["UNKNOWN"],
                rt_cd=rt_cd,
                msg_cd=msg_cd,
                msg1=msg1,
                error_code=error_code,
                error_description=error_description,
                warning_code=alignment.warning_code,
                domain_mode=alignment.mode,
                expected_base_url=alignment.expected_base_url,
            )
            raise TokenIssueError(
                f"Token issue failed: status={resp.status_code} rt_cd={rt_cd} msg_cd={msg_cd} msg1={msg1} warning_code={alignment.warning_code}"
            )

        token = KisToken(
            access_token=resp.body["access_token"],
            token_type=resp.body.get("token_type", "Bearer"),
            expires_in=resp.body.get("expires_in", 86400),
            issued_at=datetime.now(timezone.utc),
        )
        self._cached_token = token
        self._last_diagnostic = None
        return token

    def __repr__(self) -> str:
        return f"KisTokenProvider(app_key=****, base_url={self._base_url})"
