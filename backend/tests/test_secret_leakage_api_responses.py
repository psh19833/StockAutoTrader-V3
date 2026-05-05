from __future__ import annotations

import json

import pytest


KEYWORDS = [
    "appkey",
    "appsecret",
    "access_token",
    "approval_key",
    "telegram_bot_token",
    "TELEGRAM_BOT_TOKEN",
    "KIS_APP_SECRET",
    "secret raw value",
    "token raw value",
]


def _assert_no_secret_like(obj, *, allow_account_no: bool = True, allow_chat_id: bool = True):
    """Best-effort: ensure API-ish payloads do not contain secret-like strings.

    Note:
    - account_no and TELEGRAM_CHAT_ID are allowed to be displayed in dashboard.
    - but appkey/appsecret/access_token/approval_key/telegram bot token must not.
    """
    s = json.dumps(obj, ensure_ascii=False, default=str).lower()
    for k in KEYWORDS:
        assert k.lower() not in s


def test_audit_timeline_response_has_no_secret_like_strings():
    from dashboard.dashboard_routes import handle_get_audit_timeline

    items = handle_get_audit_timeline(limit=50)
    assert isinstance(items, list)
    _assert_no_secret_like(items)


def test_ws_status_response_has_reason_and_no_secret_like_strings():
    import asyncio
    from main import dashboard_ws_status

    res = asyncio.run(dashboard_ws_status())
    assert isinstance(res, dict)
    assert res.get("connection_state")
    assert res.get("status_reason")
    _assert_no_secret_like(res)


def test_audit_detail_sanitizes_payload_and_checklist_no_secret_like_strings(tmp_path):
    """Create a repo event containing secret-like fields and ensure detail response is sanitized."""
    import sqlite3

    from dashboard.dashboard_routes import get_service, handle_get_audit_event_detail
    from storage.database import init_db
    from storage.sqlite_repositories import SqliteAuditEventRepository

    svc = get_service()

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    repo = SqliteAuditEventRepository(conn)
    svc.set_audit_repository(repo)

    payload_with_secrets = {
        "note": "testing",
        "appkey": "REAL_APPKEY_1234567890",
        "appsecret": "REAL_APPSECRET_1234567890",
        "access_token": "Bearer REAL_ACCESS_TOKEN_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "approval_key": "REAL_APPROVAL_KEY_1234567890",
        "telegram_bot_token": "123456789:AAAAAAAAAAAAAAAAAAAAAA",
        "TELEGRAM_BOT_TOKEN": "123456789:BBBBBBBBBBBBBBBBBBBBBB",
        "KIS_APP_SECRET": "SOME_SECRET",
        "checklist": {
            "schema_version": "v1",
            "items": [
                {
                    "key": "risk.allowed",
                    "label": "Risk allowed",
                    "status": "PASS",
                    "value": True,
                    "threshold": True,
                    "reason": "ok",
                    "source": "risk",
                    "evaluated_at": "2026-01-01T00:00:00Z",
                }
            ],
        },
    }

    event_id = "evt_secret_leak_test"
    repo.save(
        {
            "event_id": event_id,
            "event_time": "2026-01-01T00:00:00Z",
            "event_type": "TEST",
            "severity": "INFO",
            "source": "unit_test",
            "symbol": "005930",
            "strategy_name": "",
            "status": "",
            "summary": "summary should not contain secrets",
            "correlation_id": "corr-1",
            "payload": payload_with_secrets,
            "has_checklist": 1,
        }
    )

    detail = handle_get_audit_event_detail(event_id)
    assert isinstance(detail, dict)
    assert detail.get("event_id") == event_id

    # Must not leak keywords anywhere in response
    _assert_no_secret_like(detail)


def test_telegram_test_without_confirm_no_secret_like_strings():
    import asyncio
    from main import telegram_test

    res = asyncio.run(telegram_test({}))
    assert res["sent"] is False
    assert res.get("mode") == "dry-run"
    _assert_no_secret_like(res)


def test_telegram_test_with_confirm_uses_mock_sender_and_no_secret_like_strings(monkeypatch):
    import asyncio

    import main
    from notifications.telegram_sender import InMemoryTelegramSender

    # Patch sender factory to prevent real network calls.
    sender = InMemoryTelegramSender(should_fail=False)

    def _fake_factory():
        return sender

    monkeypatch.setattr(main, "_get_telegram_sender", _fake_factory)

    res = asyncio.run(main.telegram_test({"confirm": "SEND_TEST_TELEGRAM"}))
    assert res["sent"] is True
    _assert_no_secret_like(res)

    # Ensure it actually used our in-memory sender (one event recorded)
    assert sender.sent_count == 1
