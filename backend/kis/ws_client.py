"""KIS WebSocket Client — interface, stub, and guarded real client.

WebSocketClient: Protocol interface for connect/disconnect/subscribe/unsubscribe.
StubWebSocketClient: Test-only implementation (no network calls).
GuardedRealWebSocketClient: Skeleton for production use (not connected in tests).

Reconnect/backoff 설정은 ReconnectConfig 모델을 통해 제어.
ConnectionStatus는 별도 모델(WebSocketConnectionStatus)로 Dashboard에서 조회 가능.
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from kis.ws_models import WebSocketMessageBase, WebSocketConnectionStatus
from kis.ws_subscription import (
    build_subscribe_payload,
    build_unsubscribe_payload,
    MASKED_APPROVAL_KEY,
)


# ── Reconnect Config ─────────────────────────────────────────────────────────

class ReconnectConfig:
    """WebSocket 재연결 및 backoff 설정."""

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier

    def compute_delay(self, attempt: int) -> float:
        """지수 backoff delay 계산 (capped at max_delay).

        Args:
            attempt: 0-index 재연결 시도 횟수
        """
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay)


# ── Connection State Enum ────────────────────────────────────────────────────

class ConnectionState(Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


# ── WebSocketClient Interface ────────────────────────────────────────────────

class WebSocketClient(ABC):
    """WebSocket client protocol.

    All implementations must support connect/disconnect/subscribe/unsubscribe
    and provide a WebSocketConnectionStatus via get_status().
    """

    @abstractmethod
    def connect(self, approval_key: str = "", base_url: str = "") -> None:
        """Establish WebSocket connection using approval_key."""

    @abstractmethod
    def disconnect(self) -> None:
        """Gracefully close WebSocket connection."""

    @abstractmethod
    def subscribe(self, tr_id: str, symbol: str) -> None:
        """Subscribe to a real-time data channel.

        Args:
            tr_id: KIS TR_ID (e.g., "H0STCNT0")
            symbol: stock code (e.g., "005930")
        """

    @abstractmethod
    def unsubscribe(self, tr_id: str) -> None:
        """Unsubscribe from a data channel."""

    @abstractmethod
    def get_status(self) -> WebSocketConnectionStatus:
        """Return current connection and subscription status."""


# ── StubWebSocketClient (test only) ──────────────────────────────────────────

class StubWebSocketClient(WebSocketClient):
    """Test-only WebSocket client — no real network connections.

    Supports:
      - State transitions (connect/disconnect/error)
      - Channel subscription tracking
      - Message injection for testing downstream handlers
      - Reconnect/backoff simulation
      - Data quality warning accumulation
    """

    def __init__(self, reconnect_config: Optional[ReconnectConfig] = None):
        self._connection_state = ConnectionState.DISCONNECTED
        self._subscribed: dict[str, str] = {}  # tr_id -> symbol
        self._last_message_at: Optional[datetime] = None
        self._reconnect_count = 0
        self._last_error_type: Optional[str] = None
        self._data_quality_warnings: list[str] = []
        self._reconnect_config = reconnect_config or ReconnectConfig()
        # For testing: store injected messages
        self.received_messages: list[WebSocketMessageBase] = []

    def connect(self, approval_key: str = "", base_url: str = "") -> None:
        self._connection_state = ConnectionState.CONNECTED

    def disconnect(self) -> None:
        self._connection_state = ConnectionState.DISCONNECTED
        self._subscribed.clear()

    def subscribe(self, tr_id: str, symbol: str) -> None:
        if self._connection_state != ConnectionState.CONNECTED:
            raise RuntimeError(
                f"Cannot subscribe when {self._connection_state.value}"
            )
        self._subscribed[tr_id] = symbol

    def unsubscribe(self, tr_id: str) -> None:
        self._subscribed.pop(tr_id, None)

    def get_status(self) -> WebSocketConnectionStatus:
        return WebSocketConnectionStatus(
            connection_state=self._connection_state.value,
            subscribed_channels=list(self._subscribed.keys()),
            last_message_at=self._last_message_at,
            reconnect_count=self._reconnect_count,
            last_error_type=self._last_error_type,
            data_quality_warnings=list(self._data_quality_warnings),
        )

    # ── Stub helpers for test injection ────────────────────────────────────

    def _inject_message(self, message: WebSocketMessageBase) -> None:
        """Inject a real-time message (for testing o11y/event handlers)."""
        self._last_message_at = datetime.now(timezone.utc)
        self.received_messages.append(message)

    def _simulate_reconnect(self) -> None:
        """Simulate a reconnect cycle."""
        self._connection_state = ConnectionState.RECONNECTING
        self._reconnect_count += 1
        self._connection_state = ConnectionState.CONNECTED

    def _simulate_error(self, error_type: str) -> None:
        """Simulate a connection error."""
        self._connection_state = ConnectionState.ERROR
        self._last_error_type = error_type

    def _add_data_quality_warning(self, warning: str) -> None:
        self._data_quality_warnings.append(warning)

    def _heartbeat(self) -> None:
        """Simulate heartbeat, updating last_message_at."""
        self._last_message_at = datetime.now(timezone.utc)


# ── GuardedRealWebSocketClient (production skeleton) ─────────────────────────

class GuardedRealWebSocketClient(WebSocketClient):
    """Production WebSocket client skeleton.

    현재는 구조만 정의되어 있으며, 실제 KIS WebSocket 연결은
    추후 활성화된다. connect() 호출 시 NotImplementedError 발생.

    활성화 조건:
      - approval_key 발급 완료
      - KIS WebSocket endpoint URL 설정
      - 주문 endpoint 차단 유지

    N8-B:
      - build_subscribe_payload / build_unsubscribe_payload 추가
      - get_subscribe_payload_masked: display/log 용 마스킹 버전
      - _store_approval_key: 내부 저장 (repr 미노출)
    """

    def __init__(self, reconnect_config: Optional[ReconnectConfig] = None):
        self._reconnect_config = reconnect_config or ReconnectConfig()
        self._connection_state = ConnectionState.DISCONNECTED
        self._subscribed: dict[str, str] = {}
        self._last_message_at: Optional[datetime] = None
        self._reconnect_count = 0
        self._last_error_type: Optional[str] = None
        self._data_quality_warnings: list[str] = []
        self._approval_key: Optional[str] = None
        self._base_url: str = ""

    def _store_approval_key(self, approval_key: str) -> None:
        """Store approval_key internally (never exposed in repr/log)."""
        self._approval_key = approval_key

    def build_subscribe_payload(self, tr_id: str, symbol: str,
                                 approval_key: str) -> dict:
        """Build wire-level subscribe payload.

        approval_key is included in the returned dict for actual
        WebSocket transmission. Use get_subscribe_payload_masked()
        for display/log output.
        """
        return build_subscribe_payload(tr_id, symbol, approval_key)

    def build_unsubscribe_payload(self, tr_id: str, symbol: str,
                                   approval_key: str) -> dict:
        """Build wire-level unsubscribe payload."""
        return build_unsubscribe_payload(tr_id, symbol, approval_key)

    def get_subscribe_payload_masked(self, tr_id: str, symbol: str,
                                      approval_key: str) -> str:
        """Return subscribe payload as JSON string with approval_key masked.

        Safe for display/log output.
        """
        payload = build_subscribe_payload(tr_id, symbol, approval_key)
        payload["header"]["approval_key"] = MASKED_APPROVAL_KEY
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def connect(self, approval_key: str = "", base_url: str = "") -> None:
        """Reserved for production WebSocket connection.

        Raises:
            NotImplementedError: 아직 실제 연결 구현 전.
        """
        raise NotImplementedError(
            "Real KIS WebSocket connection is not yet implemented. "
            "Use StubWebSocketClient for testing."
        )

    def __repr__(self) -> str:
        return (
            f"GuardedRealWebSocketClient("
            f"state={self._connection_state.value}, "
            f"subscribed={list(self._subscribed.keys())})"
        )

    def disconnect(self) -> None:
        self._connection_state = ConnectionState.DISCONNECTED

    def subscribe(self, tr_id: str, symbol: str) -> None:
        self._subscribed[tr_id] = symbol

    def unsubscribe(self, tr_id: str) -> None:
        self._subscribed.pop(tr_id, None)

    def get_status(self) -> WebSocketConnectionStatus:
        return WebSocketConnectionStatus(
            connection_state=self._connection_state.value,
            subscribed_channels=list(self._subscribed.keys()),
            last_message_at=self._last_message_at,
            reconnect_count=self._reconnect_count,
            last_error_type=self._last_error_type,
            data_quality_warnings=list(self._data_quality_warnings),
        )
