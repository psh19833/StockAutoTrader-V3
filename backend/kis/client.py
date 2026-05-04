"""KIS API Client — 단일 API 호출 진입점

SAT3의 모든 KIS REST API 호출은 이 Client를 통해 이루어진다.
Phase 1에서는 실제 HTTP 호출 없이 구조와 정책 연결만 구현한다.

주요 기능:
- base_url 관리 (실전 URL 고정, 모의투자 없음)
- headers 생성 (content-type, tr_id)
- Rate Limiter 통합
- Auth Manager 통합
- Source Policy 검증 연동
- DataUnavailable 생성
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from kis.auth import KisAuthManager
from kis.endpoints import KisEndpoint, get_endpoint, is_order_endpoint, EndpointNotFoundError
from kis.rate_limit import KisRateLimiter
from kis.schemas import DataUnavailable
from kis.source_policy import SourcePolicy


# KIS 실전 서버 URL (모의투자 금지 — 고정)
KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"


class KisClient:
    """KIS API Client

    모든 KIS REST 호출의 단일 진입점.
    Phase 1에서는 구조, 정책 연결, 헤더/URL 준비까지 구현.
    실제 HTTP 호출과 주문 실행은 이후 Phase에서 구현.
    """

    def __init__(
        self,
        base_url: str | None = None,
        rate_limiter: KisRateLimiter | None = None,
        auth_manager: KisAuthManager | None = None,
        source_policy: SourcePolicy | None = None,
    ):
        self.base_url = base_url or KIS_REAL_BASE_URL
        self.rate_limiter = rate_limiter or KisRateLimiter()
        self.auth_manager = auth_manager or KisAuthManager()
        self.source_policy = source_policy or SourcePolicy()

    def _build_url(self, path: str) -> str:
        """전체 URL 빌드

        Args:
            path: API 경로

        Returns:
            전체 URL 문자열
        """
        return f"{self.base_url}{path}"

    def _prepare_headers(
        self,
        tr_id: str | None = None,
        requires_auth: bool = True,
    ) -> dict[str, str]:
        """HTTP 요청 헤더 준비

        Args:
            tr_id: KIS TR ID (선택)
            requires_auth: 인증 헤더 포함 여부

        Returns:
            헤더 딕셔너리
        """
        headers: dict[str, str] = {
            "content-type": "application/json",
        }

        if tr_id:
            headers["tr_id"] = tr_id

        if requires_auth:
            auth_headers = self.auth_manager.get_authorization_header()
            headers.update(auth_headers)

        return headers

    def get_endpoint_info(self, name: str) -> KisEndpoint:
        """Endpoint 정보 조회

        Args:
            name: endpoint 식별자

        Returns:
            KisEndpoint 객체

        Raises:
            EndpointNotFoundError: 찾을 수 없는 경우
        """
        return get_endpoint(name)

    def is_order_endpoint(self, name: str) -> bool:
        """주문 endpoint 여부 확인

        Args:
            name: endpoint 식별자

        Returns:
            주문 endpoint면 True
        """
        return is_order_endpoint(name)

    def data_unavailable(
        self,
        reason_code: str,
        reason_text: str,
        endpoint: str,
        request_id: str | None = None,
    ) -> DataUnavailable:
        """DataUnavailable 객체 생성

        API 실패 시 추정값을 만들지 않고 DataUnavailable을 반환한다.

        Args:
            reason_code: 실패 원인 코드
            reason_text: 실패 설명
            endpoint: 실패가 발생한 API 엔드포인트
            request_id: 요청 식별자 (선택)

        Returns:
            DataUnavailable 객체
        """
        return DataUnavailable(
            reason_code=reason_code,
            reason_text=reason_text,
            endpoint=endpoint,
            fetched_at=datetime.now(timezone.utc),
            request_id=request_id,
        )