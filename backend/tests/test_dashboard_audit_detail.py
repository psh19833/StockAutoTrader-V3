from __future__ import annotations

from dashboard.dashboard_service import DashboardService
from dashboard.dashboard_models import AuditTimelineView


def test_dashboard_audit_detail_returns_sanitized_payload_and_checklist():
    svc = DashboardService()

    timeline = AuditTimelineView(
        event_type="CANDIDATE_DISCOVERED",
        correlation_id="scan_001",
        symbol="005930",
        timestamp="2026-05-05T09:00:00Z",
        event_id="evt_001",
        severity="INFO",
        summary="",
    )
    svc.inject_audit_events([timeline])

    svc.inject_audit_event_payloads(
        {
            "evt_001": {
                "checklist": {
                    "schema_version": "1.0",
                    "items": [],
                    "telegram_bot_token": "123456:AAAAAAAAAAAAAAAAAAAAAA",
                },
                "access_token": "SECRET_TOKEN_SHOULD_BE_MASKED",
            }
        }
    )

    detail = svc.get_audit_event_detail("evt_001")
    assert detail["event_id"] == "evt_001"
    assert detail["checklist"] is not None

    # sanitizer should mask secrets (exact mask pattern not asserted, only presence of ****)
    payload = detail["payload_sanitized"]
    assert "access_token" in payload
    assert "****" in str(payload["access_token"])
    assert "checklist" in payload
