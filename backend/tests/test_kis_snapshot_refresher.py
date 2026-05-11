from __future__ import annotations

from datetime import datetime, timedelta, timezone

from runtime.kis_snapshot_refresher import KisReadonlySnapshotRefresher


class _DummyService:
    def __init__(self, rest_ts: str, ws_ts: str):
        self._rest = {"timestamp": rest_ts, "success": True, "price": "OK (1 won)"}
        self._ws = {"timestamp": ws_ts, "success": True, "connection_state": "CONNECTED"}

    def _parse_iso_dt(self, raw: str):
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None

    def _load_rest_smoke_snapshot(self):
        return dict(self._rest)

    def _load_ws_smoke_snapshot(self):
        return dict(self._ws)


def _fresh(seconds: int = 30) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _stale(seconds: int = 600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def test_auto_refresh_disabled_no_attempt(monkeypatch):
    svc = _DummyService(_stale(), _stale())
    ref = KisReadonlySnapshotRefresher(svc)
    monkeypatch.setenv("SAT3_KIS_SNAPSHOT_AUTO_REFRESH_ENABLED", "false")

    out = ref.maybe_refresh(mode="live", session="REGULAR_MARKET")
    assert out["enabled"] is False
    assert out["reason"] == "auto_refresh_disabled"


def test_interval_not_reached_no_refresh(monkeypatch):
    svc = _DummyService(_fresh(20), _fresh(20))
    ref = KisReadonlySnapshotRefresher(svc)
    monkeypatch.setenv("SAT3_KIS_SNAPSHOT_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("SAT3_KIS_REST_REFRESH_INTERVAL_SECONDS", "180")
    monkeypatch.setenv("SAT3_KIS_WS_REFRESH_INTERVAL_SECONDS", "180")

    out = ref.maybe_refresh(mode="live", session="REGULAR_MARKET")
    assert out["enabled"] is True
    assert out["rest_attempted"] is False
    assert out["ws_attempted"] is False


def test_rest_ws_stale_attempt_refresh(monkeypatch):
    svc = _DummyService(_stale(), _stale())
    ref = KisReadonlySnapshotRefresher(svc)
    monkeypatch.setenv("SAT3_KIS_SNAPSHOT_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("SAT3_KIS_REST_REFRESH_INTERVAL_SECONDS", "180")
    monkeypatch.setenv("SAT3_KIS_WS_REFRESH_INTERVAL_SECONDS", "180")
    monkeypatch.setattr(ref, "_run_rest_refresh", lambda: True)
    monkeypatch.setattr(ref, "_run_ws_refresh", lambda: True)

    out = ref.maybe_refresh(mode="live", session="REGULAR_MARKET")
    assert out["rest_attempted"] is True
    assert out["rest_ok"] is True
    assert out["ws_attempted"] is True
    assert out["ws_ok"] is True


def test_refresh_exception_is_contained(monkeypatch):
    svc = _DummyService(_stale(), _stale())
    ref = KisReadonlySnapshotRefresher(svc)
    monkeypatch.setenv("SAT3_KIS_SNAPSHOT_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setattr(ref, "_run_rest_refresh", lambda: (_ for _ in ()).throw(RuntimeError("x")))

    out = ref.maybe_refresh(mode="live", session="REGULAR_MARKET")
    assert out["enabled"] is True
    assert out["reason"] == "refresh_exception"


def test_live_only_mode_skip(monkeypatch):
    svc = _DummyService(_stale(), _stale())
    ref = KisReadonlySnapshotRefresher(svc)
    monkeypatch.setenv("SAT3_KIS_SNAPSHOT_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("SAT3_KIS_SNAPSHOT_REFRESH_LIVE_ONLY", "true")

    out = ref.maybe_refresh(mode="dry-run", session="REGULAR_MARKET")
    assert out["skipped"] is True
    assert out["reason"] == "mode_not_live"
