"""AuditEvent <-> Repository bridge.

Purpose:
- Persist operational AuditEvent into AuditEventRepository (SQLite) for live timeline.
- Persist only sanitized payload (no raw REST/WS, no secrets).

This module is safe to use in runtime and tests.
"""

from __future__ import annotations

from typing import Any

from audit_logging.audit_event import AuditEvent
from audit_logging.log_sanitizer import sanitize_dict
from storage.repositories import AuditEventRepository


def audit_event_to_repo_dict(event: AuditEvent) -> dict[str, Any]:
    payload_sanitized = sanitize_dict(event.payload) if isinstance(event.payload, dict) else {}

    return {
        "event_id": event.event_id,
        "event_time": event.event_time.isoformat() if event.event_time else "",
        "event_type": event.event_type,
        "severity": event.severity,
        "source": event.source,
        "symbol": event.symbol or "",
        "strategy_name": event.strategy_name or "",
        "correlation_id": event.correlation_id or "",
        # Persist sanitized payload only
        "payload": payload_sanitized,
    }


def save_audit_event(repo: AuditEventRepository, event: AuditEvent) -> int:
    """Save AuditEvent into repository."""
    return repo.save(audit_event_to_repo_dict(event))
