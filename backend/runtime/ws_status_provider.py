"""WebSocket status provider (DI-only).

We do not connect to real KIS WebSocket in this phase.
This module provides an interface so /api/dashboard/ws-status can reflect real runtime state when available.

Rules:
- Provider must not expose secrets.
- When provider is not configured, API must return safe status with reason.
"""

from __future__ import annotations

from typing import Protocol


class WsStatusProvider(Protocol):
    def get_status(self) -> dict:
        """Return sanitized ws status.

        Expected fields (example):
          - connection_state: CONNECTED | DISCONNECTED | UNKNOWN
          - subscribed_channels: list[str]
          - updated_at: ISO8601 string (optional)
        """
        raise NotImplementedError
