from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RefreshResult:
    rest_attempted: bool = False
    rest_ok: bool = False
    ws_attempted: bool = False
    ws_ok: bool = False
    reason: str = ""


class KisReadonlySnapshotRefresher:
    """Readonly REST/WS smoke snapshot auto-refresher.

    Safety:
    - readonly smoke only
    - no order API calls
    - no fake success writes
    - exceptions are contained
    """

    def __init__(self, service) -> None:
        self._service = service
        self._lock = threading.Lock()

    def _env_bool(self, key: str, default: bool = False) -> bool:
        raw = str(os.getenv(key, "true" if default else "false")).strip().lower()
        return raw in {"1", "true", "yes", "on", "y"}

    def _env_int(self, key: str, default: int) -> int:
        try:
            return int(str(os.getenv(key, str(default))).strip())
        except Exception:
            return default

    def _snapshot_age_seconds(self, snapshot: dict[str, Any] | None) -> int:
        if not isinstance(snapshot, dict):
            return 10**9
        ts = str(snapshot.get("timestamp", "") or "")
        dt = self._service._parse_iso_dt(ts)  # existing parser in DashboardService
        if dt is None:
            return 10**9
        return int((datetime.now(timezone.utc) - dt).total_seconds())

    def _run_rest_refresh(self) -> bool:
        from kis.transport import RealTransport
        from scripts.kis_readonly_smoke import run_smoke_with_transport, _save_snapshot

        app_key = os.getenv("KIS_APP_KEY", "")
        app_secret = os.getenv("KIS_APP_SECRET", "")
        base_url = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
        account_no = os.getenv("KIS_ACCOUNT_NO", "")
        symbol = os.getenv("SAT3_KIS_REST_REFRESH_SYMBOL", "005930")

        if not app_key or not app_secret:
            return False

        old_live = os.getenv("LIVE_TRADING_ENABLED", "")
        try:
            os.environ["LIVE_TRADING_ENABLED"] = "false"
            transport = RealTransport(base_url=base_url, timeout=20)
            result = run_smoke_with_transport(
                transport=transport,
                symbol=symbol,
                app_key=app_key,
                app_secret=app_secret,
                base_url=base_url,
                account_no=account_no,
            )
            _save_snapshot(result)
            return bool(str(result.get("token", "")).startswith("OK") and str(result.get("price", "")).startswith("OK"))
        except Exception:
            return False
        finally:
            if old_live == "":
                os.environ.pop("LIVE_TRADING_ENABLED", None)
            else:
                os.environ["LIVE_TRADING_ENABLED"] = old_live

    def _run_ws_refresh(self) -> bool:
        duration = max(5, self._env_int("SAT3_KIS_WS_REFRESH_DURATION_SECONDS", 20))
        max_messages = max(1, self._env_int("SAT3_KIS_WS_REFRESH_MAX_MESSAGES", 8))
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "kis_ws_readonly_smoke.py"

        env = os.environ.copy()
        env["LIVE_TRADING_ENABLED"] = "false"

        cmd = [
            sys.executable,
            str(script_path),
            "--real-ws",
            "--duration",
            str(duration),
            "--max-messages",
            str(max_messages),
        ]
        try:
            completed = subprocess.run(
                cmd,
                env=env,
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,
                text=True,
                timeout=max(30, duration + 20),
                check=False,
            )
            return completed.returncode == 0
        except Exception:
            return False

    def maybe_refresh(self, *, mode: str, session: str) -> dict[str, Any]:
        enabled = self._env_bool("SAT3_KIS_SNAPSHOT_AUTO_REFRESH_ENABLED", default=False)
        if not enabled:
            return {"enabled": False, "reason": "auto_refresh_disabled"}

        run_in_live_only = self._env_bool("SAT3_KIS_SNAPSHOT_REFRESH_LIVE_ONLY", default=True)
        if run_in_live_only and mode != "live":
            return {"enabled": True, "skipped": True, "reason": "mode_not_live"}

        if session not in {"REGULAR_MARKET", "UNKNOWN"}:
            return {"enabled": True, "skipped": True, "reason": f"session_{session}"}

        if not self._lock.acquire(blocking=False):
            return {"enabled": True, "skipped": True, "reason": "refresh_in_progress"}

        try:
            rest_interval = max(120, self._env_int("SAT3_KIS_REST_REFRESH_INTERVAL_SECONDS", 180))
            ws_interval = max(120, self._env_int("SAT3_KIS_WS_REFRESH_INTERVAL_SECONDS", 180))

            rest_snapshot = self._service._load_rest_smoke_snapshot()
            ws_snapshot = self._service._load_ws_smoke_snapshot()
            rest_age = self._snapshot_age_seconds(rest_snapshot)
            ws_age = self._snapshot_age_seconds(ws_snapshot)

            res = RefreshResult(reason="no_refresh_needed")

            if rest_age >= rest_interval:
                res.rest_attempted = True
                res.rest_ok = self._run_rest_refresh()
                res.reason = "rest_refresh_attempted"

            # WS more conservative: only when stale enough and either live mode or rest just refreshed
            if ws_age >= ws_interval:
                res.ws_attempted = True
                res.ws_ok = self._run_ws_refresh()
                res.reason = "ws_refresh_attempted" if not res.rest_attempted else "rest_ws_refresh_attempted"

            return {
                "enabled": True,
                "rest_interval": rest_interval,
                "ws_interval": ws_interval,
                "rest_age_before": rest_age,
                "ws_age_before": ws_age,
                "rest_attempted": res.rest_attempted,
                "rest_ok": res.rest_ok,
                "ws_attempted": res.ws_attempted,
                "ws_ok": res.ws_ok,
                "reason": res.reason,
            }
        except Exception as e:
            return {
                "enabled": True,
                "error": f"{type(e).__name__}",
                "reason": "refresh_exception",
            }
        finally:
            self._lock.release()
