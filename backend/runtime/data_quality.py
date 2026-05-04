"""Data quality checks for market data.

Staleness, missing fields, source validation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


class DataQualityCheck:
    """Checks data quality of market data entries."""

    DEFAULT_STALE_SECONDS = 60

    @staticmethod
    def is_stale(
        timestamp: Optional[datetime],
        threshold_seconds: int = DEFAULT_STALE_SECONDS,
    ) -> bool:
        """Return True if data is older than threshold."""
        if timestamp is None:
            return True
        age = datetime.now(timezone.utc) - timestamp
        return age > timedelta(seconds=threshold_seconds)

    @staticmethod
    def has_missing_fields(data: dict, required: list[str]) -> list[str]:
        """Return list of missing required fields."""
        return [f for f in required if f not in data or data[f] is None]

    @staticmethod
    def is_valid_source(source: str) -> bool:
        """Only KIS_API_REST and KIS_API_WS are valid sources."""
        return source in ("KIS_API_REST", "KIS_API_WS")

    @staticmethod
    def check_ws_disconnect_risk(
        ws_connected: bool,
        last_ws_message_at: Optional[datetime],
        threshold_seconds: int = 30,
    ) -> list[str]:
        """Return warnings if WS is or may be disconnected."""
        warnings = []
        if not ws_connected:
            warnings.append("WS_DISCONNECTED")
        elif last_ws_message_at and DataQualityCheck.is_stale(
            last_ws_message_at, threshold_seconds
        ):
            warnings.append("WS_STALE_DATA")
        return warnings
