"""KIS WebSocket subscription request builder.

WebSocket 실시간 데이터 구독/해지를 위한 payload 빌더.
approval_key는 secret으로 취급하며, 모든 repr/str 출력 시 마스킹한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


MASKED_APPROVAL_KEY: str = "****-****-****"


@dataclass(frozen=True)
class SubscribeRequest:
    """Single channel subscription request.

    Notes:
      - approval_key 원문은 repr/str/log에 노출 금지
      - get_approval_key()로만 실제 키 접근 (내부 WebSocket 연결용)
    """

    tr_id: str
    symbol: str
    approval_key: str
    channel_name: str = ""

    def get_approval_key(self) -> str:
        """Return the real approval key (internal use only)."""
        return self.approval_key

    def get_masked_approval_key(self) -> str:
        """Return masked approval key for display/logging."""
        return MASKED_APPROVAL_KEY

    def __repr__(self) -> str:
        return (
            f"SubscribeRequest(tr_id={self.tr_id!r}, "
            f"symbol={self.symbol!r}, "
            f"approval_key={MASKED_APPROVAL_KEY})"
        )

    def __str__(self) -> str:
        return (
            f"SubscribeRequest(tr_id={self.tr_id}, "
            f"symbol={self.symbol}, "
            f"approval_key={MASKED_APPROVAL_KEY})"
        )


def build_subscribe_payload(
    tr_id: str,
    symbol: str,
    approval_key: str,
) -> dict:
    """Build KIS WebSocket subscribe (register) payload.

    Returns the wire-format payload. Caller (smoke script) is responsible
    for masking the approval_key before any display/log output.

    Args:
        tr_id: KIS TR_ID (e.g., "H0STCNT0")
        symbol: stock code (e.g., "005930")
        approval_key: real approval_key from WsApprovalKey
    """
    return {
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1",   # 1 = register (subscribe)
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": symbol,
            },
        },
    }


def build_unsubscribe_payload(
    tr_id: str,
    symbol: str,
    approval_key: str,
) -> dict:
    """Build KIS WebSocket unsubscribe (unregister) payload.

    Args:
        tr_id: KIS TR_ID
        symbol: stock code
        approval_key: real approval_key
    """
    return {
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "2",   # 2 = unregister (unsubscribe)
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": symbol,
            },
        },
    }
