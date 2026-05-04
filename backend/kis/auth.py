"""KIS API OAuth 인증 관리

Access Token의 발급, 갱신, 상태 관리를 담당한다.
SAT3에서는 실제 KIS API의 OAuth2 인증을 사용하며,
모의투자/가상 토큰을 사용하지 않는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable


class TokenState(Enum):
    """Access Token 상태"""
    NONE = "NONE"           # 토큰 없음
    VALID = "VALID"         # 유효
    EXPIRED = "EXPIRED"     # 만료
    REFRESHING = "REFRESHING"  # 갱신 중


class InvalidTokenError(Exception):
    """유효하지 않은 토큰 사용 시도"""
    pass


class TokenExpiredError(InvalidTokenError):
    """만료된 토큰 사용 시도"""
    pass


@dataclass(frozen=True)
class KisToken:
    """KIS API Access Token

    Attributes:
        access_token: JWT 형식의 Access Token
        token_type: 토큰 타입 (항상 "Bearer")
        expires_in: 토큰 유효 시간 (초)
        issued_at: 토큰 발급 시각 (UTC)
    """
    access_token: str
    token_type: str
    expires_in: int
    issued_at: datetime

    @property
    def expires_at(self) -> datetime:
        """토큰 만료 시각"""
        return self.issued_at + timedelta(seconds=self.expires_in)

    @property
    def is_expired(self) -> bool:
        """토큰 만료 여부"""
        return datetime.now(timezone.utc) >= self.expires_at


@dataclass
class AuthConfig:
    """인증 설정

    Attributes:
        token_refresh_margin: 만료 N초 전부터 refresh 시작 (기본 3600초 = 1시간)
    """
    token_refresh_margin: int = 3600


class KisAuthManager:
    """KIS API Access Token 생명주기 관리자

    - 토큰 상태 추적 (NONE → VALID → EXPIRED)
    - 토큰 갱신 콜백 기반 자동 갱신
    - 만료 임박 감지 (설정 가능한 margin)
    """

    def __init__(
        self,
        margin_seconds: int = 3600,
        app_key: str | None = None,
        app_secret: str | None = None,
    ):
        self._token: KisToken | None = None
        self._margin_seconds = margin_seconds
        self._refresh_callback: Callable[[], KisToken] | None = None
        # 환경변수에서 fallback
        self._app_key = app_key or os.getenv("KIS_APP_KEY", "")
        self._app_secret = app_secret or os.getenv("KIS_APP_SECRET", "")

    def set_token(self, token: KisToken) -> None:
        """Access Token 설정"""
        self._token = token

    def get_token(self) -> KisToken | None:
        """현재 Access Token 반환"""
        return self._token

    def clear_token(self) -> None:
        """Access Token 제거"""
        self._token = None

    def get_state(self) -> TokenState:
        """현재 토큰 상태 반환"""
        if self._token is None:
            return TokenState.NONE
        if self._token.is_expired:
            return TokenState.EXPIRED
        return TokenState.VALID

    def needs_refresh(self) -> bool:
        """토큰 갱신이 필요한지 확인

        Returns:
            토큰이 없거나, 만료되었거나, 만료 임박(설정된 margin 이내)이면 True
        """
        if self._token is None:
            return True
        if self._token.is_expired:
            return True
        # 만료 임박 확인 (margin 이내)
        remaining = (self._token.expires_at - datetime.now(timezone.utc)).total_seconds()
        return remaining <= self._margin_seconds

    def require_valid_token(self) -> KisToken:
        """유효한 토큰을 요구. 없거나 만료면 예외 발생

        Returns:
            유효한 KisToken

        Raises:
            InvalidTokenError: 토큰이 없는 경우
            TokenExpiredError: 토큰이 만료된 경우
        """
        if self._token is None:
            raise InvalidTokenError("No token available. Call refresh_token() first.")
        if self._token.is_expired:
            raise TokenExpiredError("Token has expired. Call refresh_token() to renew.")
        return self._token

    def get_authorization_header(self) -> dict[str, str]:
        """Authorization HTTP 헤더 반환

        Returns:
            {"authorization": "Bearer <token>", "appkey": "...", "appsecret": "..."}

        Raises:
            InvalidTokenError: 유효한 토큰이 없는 경우
        """
        token = self.require_valid_token()
        return {
            "authorization": f"{token.token_type} {token.access_token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }

    def set_refresh_callback(self, callback: Callable[[], KisToken]) -> None:
        """토큰 갱신 콜백 등록

        Args:
            callback: 새 KisToken을 반환하는 콜백 함수
        """
        self._refresh_callback = callback

    def refresh_token(self) -> KisToken:
        """토큰 갱신 실행

        Returns:
            새로 발급된 KisToken

        Raises:
            RuntimeError: refresh 콜백이 등록되지 않은 경우
        """
        if self._refresh_callback is None:
            raise RuntimeError(
                "No refresh callback registered. "
                "Call set_refresh_callback() before refresh_token()."
            )
        new_token = self._refresh_callback()
        self.set_token(new_token)
        return new_token