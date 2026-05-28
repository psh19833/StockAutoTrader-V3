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
from kis.token_cache import TokenCache, app_key_fingerprint, base_url_hash


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

    def issue_token(self, *, force_token_refresh: bool = False) -> KisToken:
        if self._is_cached_token_valid():
            return self._cached_token  # type: ignore[return-value]

        if self._transport is None:
            raise RuntimeError("No transport configured")

        # 1) cache-first: try persistent file cache (outside repo)
        cache = TokenCache()
        rec = cache.load()
        if rec and cache.token_present(rec) and (cache.is_expired(rec) is False):
            # Reuse only if the cache entry matches the current credentials.
            # This avoids cross-test / cross-account contamination from an
            # existing local token cache file.
            if (
                rec.base_url_hash == base_url_hash(self._base_url) and
                rec.app_key_fingerprint == app_key_fingerprint(self._app_key)
            ):
                # Reconstruct a mathematically consistent KisToken from the cached
                # absolute timestamps. Do NOT use remaining seconds as expires_in,
                # because KisToken.expires_at = issued_at + expires_in.
                # Using remaining seconds would make expires_at fall in the past.
                expires_in = max(0, int(rec.expires_at_epoch) - int(rec.issued_at_epoch))
                token = KisToken(
                    access_token=rec.access_token,
                    token_type=(rec.token_type or "Bearer"),
                    expires_in=expires_in,
                    issued_at=datetime.fromtimestamp(int(rec.issued_at_epoch), tz=timezone.utc),
                )
                self._cached_token = token
                self._last_diagnostic = None
                return token

        # 2) KST 1-day guard: if we already attempted tokenP today, do not retry unless forced.
        if (not force_token_refresh) and cache.kst_attempted_today(rec) and (
            rec is None or cache.token_present(rec) is False or cache.is_expired(rec) is not False
        ):
            self._last_diagnostic = TokenIssueDiagnostic(
                error_type="KIS_TOKENP_BLOCKED_SAME_KST_DATE",
                status_code=0,
                possible_causes=["TOKENP_DAILY_POLICY"],
                rt_cd="",
                msg_cd="DAILY_TOKENP_BLOCKED",
                msg1="TokenP blocked by KST 1-day policy; wait for next window or use force flag.",
            )
            raise TokenIssueError("KIS_TOKENP_BLOCKED_SAME_KST_DATE")

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

            # persist failure meta (keep any existing valid token)
            try:
                cache.record_tokenp_attempt(
                    base_url=self._base_url,
                    app_key=self._app_key,
                    success=False,
                    failure_code=msg_cd,
                    failure_message_redacted=msg1,
                )
            except Exception:
                pass

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

        # persist token to file cache outside repo (0600). Never log token value.
        try:
            cache.record_tokenp_attempt(
                base_url=self._base_url,
                app_key=self._app_key,
                success=True,
                issued_at_utc=token.issued_at,
                expires_in=int(token.expires_in),
                token_type=str(token.token_type),
                access_token=str(token.access_token),
            )
        except Exception:
            pass

        return token

    def __repr__(self) -> str:
        return f"KisTokenProvider(app_key=****, base_url={self._base_url})"
