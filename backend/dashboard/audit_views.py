"""Dashboard Audit Views (Read-only).

- Timeline list uses AuditTimelineView (in dashboard_models.py)
- Detail view includes sanitized payload JSON + evidence checklist.

No raw REST response bodies / raw WebSocket full messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class AuditEventDetailView:
    event_id: str
    correlation_id: str = ""
    event_type: str = ""
    severity: str = "INFO"
    timestamp: str = ""
    source: str = ""
    trading_day: str = ""
    symbol: str = ""
    strategy_name: str = ""
    reason_code: str = ""
    reason_text: str = ""

    checklist: dict[str, Any] | None = None

    # Local-only advanced debug: sanitized payload JSON (collapsed by default in UI)
    payload_sanitized: dict[str, Any] = field(default_factory=dict)

    related_events: list[dict[str, Any]] = field(default_factory=list)
