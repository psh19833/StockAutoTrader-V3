from __future__ import annotations

import sqlite3
import json

from audit_logging.audit_event import AuditEvent
from audit_logging.audit_repo_bridge import save_audit_event
from dashboard.dashboard_service import DashboardService
from storage.database import init_db
from storage.sqlite_repositories import SqliteAuditEventRepository


def _mk_event(event_id: str, event_type: str, corr: str) -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        event_type=event_type,
        severity="INFO",
        correlation_id=corr,
        symbol="005930",
        strategy_name="RAPID_SURGE",
        payload={
            "checklist": {
                "schema_version": "1.0",
                "stage": "SCANNER",
                "items": [
                    {
                        "key": "scanner.included",
                        "label": "included",
                        "status": "PASS",
                        "value": True,
                        "threshold": True,
                        "reason": "",
                        "source": "scanner",
                        "evaluated_at": "2026-05-05T00:00:00Z",
                        "meta": {"unknown_field": 123},
                    }
                ],
            },
            # secrets must not survive sanitization
            "access_token": "SECRET_TOKEN",
            "approval_key": "SECRET_APPROVAL",
            "telegram_bot_token": "123456:AAAAAAAAAAAAAAAAAAAAAA",
        },
        source="scanner",
    )


def test_repo_save_then_timeline_list_includes_event_id_and_limit():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    repo = SqliteAuditEventRepository(conn)

    # Save two events
    save_audit_event(repo, _mk_event("evt_a", "SCAN_COMPLETED", "corr_1"))
    save_audit_event(repo, _mk_event("evt_b", "CANDIDATE_DISCOVERED", "corr_1"))

    svc = DashboardService()
    svc.set_audit_repository(repo)

    items = svc.get_audit_timeline(limit=1)
    assert len(items) == 1
    assert items[0].event_id in ("evt_a", "evt_b")


def test_repo_detail_by_event_id_and_related_events_and_sanitized_payload_only():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    repo = SqliteAuditEventRepository(conn)

    save_audit_event(repo, _mk_event("evt_a", "SCAN_COMPLETED", "corr_1"))
    save_audit_event(repo, _mk_event("evt_b", "CANDIDATE_DISCOVERED", "corr_1"))

    svc = DashboardService()
    svc.set_audit_repository(repo)

    detail = svc.get_audit_event_detail("evt_b")
    assert detail["event_id"] == "evt_b"
    assert detail.get("error") is None

    # checklist preserved and schema_version 유지
    assert isinstance(detail["checklist"], dict)
    assert detail["checklist"]["schema_version"] == "1.0"
    assert detail["checklist"]["items"][0]["meta"]["unknown_field"] == 123

    # related_events grouped by correlation_id
    related = detail.get("related_events", [])
    assert len(related) >= 2
    assert all(r["correlation_id"] == "corr_1" for r in related)

    # payload_sanitized must not include raw secrets
    payload = detail["payload_sanitized"]
    s = json.dumps(payload)
    for forbidden in ["SECRET_TOKEN", "SECRET_APPROVAL", "AAAAAAAAAAAAAAAAAAAAAA"]:
        assert forbidden not in s


def test_repo_detail_not_found_safe_response():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    repo = SqliteAuditEventRepository(conn)
    svc = DashboardService()
    svc.set_audit_repository(repo)

    detail = svc.get_audit_event_detail("missing_evt")
    assert detail["error"] == "not_found"
    assert detail["event_id"] == "missing_evt"
