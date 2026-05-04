"""Audit Writer — Audit Event 저장/조회/필터

초기 구현: InMemoryAuditWriter (메모리 저장)
Phase 5+에서 JSONL 파일 또는 DB 저장으로 확장 가능.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from audit_logging.audit_event import AuditEvent
from audit_logging.log_sanitizer import sanitize_payload


class AuditWriter:
    """Audit Event Writer — Append-only writer"""

    def write(self, event: AuditEvent) -> None:
        raise NotImplementedError

    def write_many(self, events: list[AuditEvent]) -> None:
        for event in events:
            self.write(event)

    def list_all(self) -> list[AuditEvent]:
        raise NotImplementedError

    def filter_by_event_type(self, event_type: str) -> list[AuditEvent]:
        return [e for e in self.list_all() if e.event_type == event_type]

    def filter_by_correlation_id(self, correlation_id: str) -> list[AuditEvent]:
        return [e for e in self.list_all() if e.correlation_id == correlation_id]

    def filter_by_severity(self, severity: str) -> list[AuditEvent]:
        return [e for e in self.list_all() if e.severity == severity]

    def filter_by_date(self, target_date: date) -> list[AuditEvent]:
        return [e for e in self.list_all() if e.trading_day == target_date]

    def filter_by_source(self, source: str) -> list[AuditEvent]:
        return [e for e in self.list_all() if e.source == source]


class InMemoryAuditWriter(AuditWriter):
    """메모리 기반 Audit Writer (초기 구현)"""

    def __init__(self):
        self._events: list[AuditEvent] = []

    def write(self, event: AuditEvent) -> None:
        sanitized_payload = sanitize_payload(event.payload)
        sanitized = AuditEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            event_time=event.event_time,
            severity=event.severity,
            correlation_id=event.correlation_id,
            trading_day=event.trading_day,
            symbol=event.symbol,
            strategy_name=event.strategy_name,
            payload=sanitized_payload,
            source=event.source,
            created_at=event.created_at,
        )
        self._events.append(sanitized)

    def list_all(self) -> list[AuditEvent]:
        return list(self._events)

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()


def audit_event_to_dict(event: AuditEvent) -> dict[str, Any]:
    """AuditEvent를 직렬화 가능한 dict로 변환"""
    d = asdict(event)
    d["event_time"] = event.event_time.isoformat() if event.event_time else None
    d["created_at"] = event.created_at.isoformat() if event.created_at else None
    d["trading_day"] = event.trading_day.isoformat() if event.trading_day else None
    return d