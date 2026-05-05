"""KIS WebSocket Approval Key management.

WebSocket 실시간 데이터 수신을 위해서는 사전에 approval_key를
발급받아야 한다. 이 모듈은 /oauth2/Approval endpoint를 통해
approval_key를 발급·관리하며, secret을 repr/str/log에 노출하지 않는다.

발급 흐름:
  1. KisCredentials를 사용해 POST /oauth2/Approval 요청
  2. 응답의 output.approval_key 추출
  3. 발급된 키는 내부 저장, 외부 노출 시 마스킹
  4. 실패 시 DataUnavailable 예외 발생 (추정값 생성 금지)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from kis.credentials import KisCredentials
from kis.transport import KisTransport, TransportResponse


class ApprovalKeyError(Exception):
    """approval_key 발급 실패 시 발생."""


MASKED_APPROVAL_KEY: str = "****-****-****"


@dataclass(frozen=True)
class ApprovalResponse:
    """/oauth2/Approval 응답 파싱 결과."""

    success: bool
    approval_key: Optional[str] = None
    rt_cd: str = ""
    msg_cd: str = ""
    msg1: str = ""

    @classmethod
    def parse(cls, body: dict) -> "ApprovalResponse":
        """Parse KIS /oauth2/Approval response body.

        Args:
            body: TransportResponse.body (dict)

        Returns:
            ApprovalResponse with success flag and parsed approval_key.
        """
        rt_cd = str(body.get("rt_cd", ""))
        msg_cd = str(body.get("msg_cd", ""))
        msg1 = str(body.get("msg1", ""))

        # Support both output.approval_key and top-level approval_key.
        output = body.get("output") if isinstance(body, dict) else None
        approval_key = None
        if isinstance(output, dict) and output.get("approval_key"):
            approval_key = output.get("approval_key")
        elif isinstance(body, dict) and body.get("approval_key"):
            approval_key = body.get("approval_key")

        # Success rules:
        # - rt_cd == "0" => success
        # - rt_cd missing but approval_key present => success
        # - rt_cd present and not "0" => failure
        if rt_cd:
            success = (rt_cd == "0")
        else:
            success = bool(approval_key)

        return cls(
            success=success,
            approval_key=approval_key if success else None,
            rt_cd=rt_cd,
            msg_cd=msg_cd,
            msg1=msg1,
        )


class ApproveRequestBuilder:
    """KIS /oauth2/Approval 요청 body 빌더."""

    @staticmethod
    def build(credentials: KisCredentials) -> dict:
        return {
            "grant_type": "client_credentials",
            "appkey": credentials.app_key,
            "secretkey": credentials.app_secret,
        }


@dataclass
class WsApprovalKey:
    """WebSocket approval key 발급·관리.

    Usage:
        approval = WsApprovalKey(credentials, transport=stub)
        approval.issue()
        masked = str(approval)          # "****-****-****"
        real_key = approval.get_approval_key()  # 실제 키 (내부 사용)

    Secret 보호:
      - __repr__ / __str__ / get_masked() 는 MASKED_APPROVAL_KEY 반환
      - get_approval_key() 로만 실제 키 접근 가능
      - credentials의 app_key/app_secret은 객체 내 노출하지 않음
    """

    credentials: KisCredentials
    transport: KisTransport
    _approval_key: Optional[str] = field(default=None, init=False, repr=False)
    _issued_at: Optional[datetime] = field(default=None, init=False, repr=False)

    def issue(self) -> str:
        """approval_key 발급.

        Returns:
            발급된 approval_key

        Raises:
            DataUnavailable: 발급 실패 시
        """
        request_body = ApproveRequestBuilder.build(self.credentials)
        resp: TransportResponse = self.transport.post_json(
            "/oauth2/Approval", json_data=request_body
        )
        parsed = ApprovalResponse.parse(resp.body)

        if not parsed.success or not parsed.approval_key:
            raise ApprovalKeyError(
                parsed.msg1 or "approval key 발급 실패"
            )

        self._approval_key = parsed.approval_key
        self._issued_at = datetime.now(timezone.utc)
        return self._approval_key

    def get_approval_key(self) -> Optional[str]:
        """실제 approval_key 반환 (로그/출력 금지, 내부 WebSocket 연결용)."""
        return self._approval_key

    def get_masked(self) -> str:
        """마스킹된 approval_key 반환."""
        return MASKED_APPROVAL_KEY

    def __str__(self) -> str:
        return MASKED_APPROVAL_KEY

    def __repr__(self) -> str:
        return f"WsApprovalKey(approval_key={MASKED_APPROVAL_KEY})"
