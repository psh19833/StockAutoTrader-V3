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
from typing import Any, Optional

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
    """Production WebSocket client with real KIS connection.

    Uses websocket-client library for actual WebSocket communication.
    Tested only via mock — never in automated tests.

    활성화 조건:
      - approval_key 발급 완료
      - KIS WebSocket endpoint URL 설정
      - 주문 endpoint 차단 유지

    Security:
      - approval_key is never exposed in repr/str/log
      - WebSocket URL is never exposed in repr/str/log
      - subscribe payload is masked when displayed
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
        self._ws: Any = None  # websocket connection object

    def _store_approval_key(self, approval_key: str) -> None:
        """Store approval_key internally (never exposed in repr/log)."""
        self._approval_key = approval_key

    def _heartbeat(self) -> None:
        """Update last_message_at for keep-alive tracking."""
        if self._connection_state == ConnectionState.CONNECTED:
            self._last_message_at = datetime.now(timezone.utc)

    def build_subscribe_payload(self, tr_id: str, symbol: str,
                                 approval_key: str) -> dict:
        return build_subscribe_payload(tr_id, symbol, approval_key)

    def build_unsubscribe_payload(self, tr_id: str, symbol: str,
                                   approval_key: str) -> dict:
        return build_unsubscribe_payload(tr_id, symbol, approval_key)

    def get_subscribe_payload_masked(self, tr_id: str, symbol: str,
                                      approval_key: str) -> str:
        payload = build_subscribe_payload(tr_id, symbol, approval_key)
        payload["header"]["approval_key"] = MASKED_APPROVAL_KEY
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def connect(self, approval_key: str = "", base_url: str = "") -> None:
        """Establish real KIS WebSocket connection.

        Uses websocket-client library. Requires valid approval_key
        and KIS WebSocket endpoint URL.

        Args:
            approval_key: Real approval_key from WsApprovalKey
            base_url: KIS WebSocket endpoint URL (e.g., ws://...)

        Raises:
            ValueError: if approval_key is empty
            ConnectionError: if WebSocket connection fails
        """
        if not approval_key:
            raise ValueError("approval_key is required for real WebSocket connection")

        self._approval_key = approval_key
        self._base_url = base_url
        self._connection_state = ConnectionState.CONNECTING

        try:
            import websocket
            self._ws = websocket.create_connection(base_url, timeout=10)
            self._connection_state = ConnectionState.CONNECTED
            self._last_message_at = datetime.now(timezone.utc)
        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            self._last_error_type = type(e).__name__
            raise ConnectionError(f"WebSocket connect failed: {e}") from e

    def disconnect(self) -> None:
        """Close WebSocket connection and reset state."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._subscribed.clear()

    def subscribe(self, tr_id: str, symbol: str) -> None:
        """Subscribe to a real-time channel via WebSocket."""
        if self._connection_state != ConnectionState.CONNECTED or not self._ws:
            raise RuntimeError(
                f"Cannot subscribe: client is {self._connection_state.value}"
            )
        payload = build_subscribe_payload(tr_id, symbol, self._approval_key or "")
        message = json.dumps(payload)
        self._ws.send(message)
        self._subscribed[tr_id] = symbol
        self._last_message_at = datetime.now(timezone.utc)

    def unsubscribe(self, tr_id: str) -> None:
        """Unsubscribe from a real-time channel via WebSocket."""
        if tr_id not in self._subscribed:
            return
        symbol = self._subscribed[tr_id]
        if self._connection_state == ConnectionState.CONNECTED and self._ws:
            payload = build_unsubscribe_payload(tr_id, symbol, self._approval_key or "")
            message = json.dumps(payload)
            try:
                self._ws.send(message)
            except Exception:
                pass
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

    def __repr__(self) -> str:
        return (
            f"GuardedRealWebSocketClient("
            f"state={self._connection_state.value}, "
            f"subscribed={list(self._subscribed.keys())})"
        )
