from __future__ import annotations

from dashboard.dashboard_routes import get_service


def test_ws_status_default_has_reason_and_no_secrets():
    svc = get_service()
    status = svc.get_ws_status()
    assert status["connection_state"] in ("UNKNOWN", "DISCONNECTED")
    assert status.get("status_reason")
    assert status.get("data_source")

    # basic secret key red flags must not be present
    joined = str(status).lower()
    for k in [
        "appkey",
        "appsecret",
        "access_token",
        "approval_key",
        "telegram_bot_token",
    ]:
        assert k not in joined
