"""SAT3 Backend FastAPI Application.

Entry point for uvicorn: uvicorn main:app --host 127.0.0.1 --port 8000
"""
import os
import threading
import time
from pathlib import Path

# Load .env from project root
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ─────────────────────────────────────────────────────────────
# Audit Repository (SQLite) for LIVE Timeline
# - Dashboard는 조회 전용이며, 저장은 audit_logging 쪽에서 수행
# - 운영에서는 파일 DB 사용, 테스트/개발은 :memory: 사용 가능
# ─────────────────────────────────────────────────────────────
try:
    import sqlite3
    from storage.database import init_db
    from storage.sqlite_repositories import SqliteAuditEventRepository
    from dashboard.dashboard_routes import get_service as _get_dashboard_service

    _db_path = os.getenv("SAT3_AUDIT_DB_PATH", "")
    if not _db_path:
        _data_dir = Path(__file__).resolve().parents[1] / "data"
        _data_dir.mkdir(parents=True, exist_ok=True)
        _db_path = str(_data_dir / "sat3_audit.db")

    _audit_conn = sqlite3.connect(_db_path, check_same_thread=False)
    _audit_conn.row_factory = sqlite3.Row
    init_db(_audit_conn)
    _audit_repo = SqliteAuditEventRepository(_audit_conn)
    _get_dashboard_service().set_audit_repository(_audit_repo)
except Exception:
    # Repository initialization failure must not prevent dashboard from starting.
    pass

app = FastAPI(title="SAT3 Dashboard API", version="3.0.0")

# Runtime scheduler loop state (read-only/dry-run dashboard refresh)
_runtime_lock = threading.Lock()
_runtime_thread = None
_runtime_stop_event = threading.Event()
_runtime_status: dict[str, object] = {
    "running": False,
    "mode": "dry-run",
    "session": "REGULAR_MARKET",
    "interval_sec": 10,
    "last_tick_at": "",
    "last_result": {},
    "tick_count": 0,
}

# Startup log — add project root to path for tools import
import sys as _sys
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)
from tools.daily_logger import DailyLogger, LogCategory
DailyLogger().log(LogCategory.SYSTEM, f"SAT3 backend started (pid={os.getpid()})")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/dashboard/summary")
async def dashboard_summary():
    from dashboard.dashboard_routes import handle_get_summary
    return handle_get_summary()


@app.get("/api/dashboard/system")
async def dashboard_system():
    from dashboard.dashboard_routes import handle_get_system
    return handle_get_system()


@app.get("/api/dashboard/session")
async def dashboard_session():
    from dashboard.dashboard_routes import handle_get_session
    return handle_get_session()


@app.get("/api/dashboard/market-regime")
async def dashboard_market_regime():
    from dashboard.dashboard_routes import handle_get_market_regime
    return handle_get_market_regime()


@app.get("/api/dashboard/ws-status")
async def dashboard_ws_status():
    """WS status endpoint.

    Safety phase behavior:
    - If a ws status provider is not configured, return a safe UNKNOWN/DISCONNECTED-like status with reason.
    - Never expose raw websocket frames or secrets.
    """
    try:
        from dashboard.dashboard_routes import get_service

        svc = get_service()
        status = svc.get_ws_status()
        return status
    except Exception:
        return {
            "connection_state": "UNKNOWN",
            "subscribed_channels": [],
            "data_source": "fallback",
            "status_reason": "ws_status_provider_not_configured",
        }


@app.get("/api/dashboard/candidates")
async def dashboard_candidates():
    from dashboard.dashboard_routes import handle_get_candidates
    return handle_get_candidates()


@app.get("/api/dashboard/quant-scores")
async def dashboard_quant_scores():
    from dashboard.dashboard_routes import handle_get_quant_scores
    return handle_get_quant_scores()


@app.get("/api/dashboard/risk-decisions")
async def dashboard_risk_decisions():
    from dashboard.dashboard_routes import handle_get_risk_decisions
    return handle_get_risk_decisions()


@app.get("/api/dashboard/orders")
async def dashboard_orders():
    from dashboard.dashboard_routes import handle_get_orders
    return handle_get_orders()


@app.get("/api/dashboard/fills")
async def dashboard_fills():
    from dashboard.dashboard_routes import handle_get_fills
    return handle_get_fills()


@app.get("/api/dashboard/portfolio")
async def dashboard_portfolio():
    from dashboard.dashboard_routes import handle_get_portfolio
    return handle_get_portfolio()


@app.get("/api/dashboard/eod")
async def dashboard_eod():
    from dashboard.dashboard_routes import handle_get_eod_latest
    return handle_get_eod_latest()


@app.get("/api/dashboard/audit")
async def dashboard_audit(limit: int = 50):
    from dashboard.dashboard_routes import handle_get_audit_timeline
    return handle_get_audit_timeline(limit)


@app.get("/api/dashboard/audit/{event_id}")
async def dashboard_audit_event_detail(event_id: str):
    from dashboard.dashboard_routes import handle_get_audit_event_detail
    return handle_get_audit_event_detail(event_id)


@app.get("/api/dashboard/telegram-status")
async def telegram_status():
    from dashboard.dashboard_routes import handle_get_telegram_status
    return handle_get_telegram_status()


@app.get("/api/dashboard/kis-account")
async def kis_account():
    from dashboard.dashboard_routes import handle_get_kis_account
    return handle_get_kis_account()


@app.get("/api/dashboard/daily-summary")
async def daily_summary(date: str = ""):
    from dashboard.dashboard_routes import handle_get_daily_summary
    return handle_get_daily_summary(date)


@app.get("/api/dashboard/strategy-breakdown")
async def strategy_breakdown(date: str = ""):
    from dashboard.dashboard_routes import handle_get_strategy_breakdown
    return handle_get_strategy_breakdown(date)


@app.get("/api/dashboard/logs")
async def dashboard_logs(date: str = "", category: str = "system", max_lines: int = 100):
    from dashboard.dashboard_routes import handle_get_logs
    return handle_get_logs(date, category, max_lines)


@app.get("/api/dashboard/log-dates")
async def log_dates():
    from dashboard.dashboard_routes import handle_get_log_dates
    return handle_get_log_dates()


def _runtime_loop() -> None:
    global _runtime_thread
    while not _runtime_stop_event.is_set():
        try:
            with _runtime_lock:
                mode = str(_runtime_status.get("mode", "dry-run"))
                session = str(_runtime_status.get("session", "REGULAR_MARKET"))
                interval_sec = int(_runtime_status.get("interval_sec", 10))
            from dashboard.dashboard_routes import run_runtime_tick_and_sync
            tick = run_runtime_tick_and_sync(mode=mode, session=session)
            with _runtime_lock:
                _runtime_status["last_result"] = tick
                _runtime_status["tick_count"] = int(_runtime_status.get("tick_count", 0)) + 1
                _runtime_status["last_tick_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception as e:
            with _runtime_lock:
                _runtime_status["last_result"] = {"error": f"{type(e).__name__}: {e}"}
        _runtime_stop_event.wait(max(1, interval_sec))

    with _runtime_lock:
        _runtime_status["running"] = False
    _runtime_thread = None


@app.post("/api/runtime/tick")
async def runtime_tick(mode: str = "dry-run", session: str = "REGULAR_MARKET"):
    from dashboard.dashboard_routes import run_runtime_tick_and_sync
    return run_runtime_tick_and_sync(mode=mode, session=session)


@app.post("/api/runtime/start")
async def runtime_start(mode: str = "dry-run", session: str = "REGULAR_MARKET", interval_sec: int = 10):
    global _runtime_thread
    with _runtime_lock:
        if _runtime_status.get("running"):
            return {"started": False, "reason": "already_running", "status": _runtime_status}

        _runtime_stop_event.clear()
        _runtime_status["running"] = True
        _runtime_status["mode"] = mode
        _runtime_status["session"] = session
        _runtime_status["interval_sec"] = max(1, int(interval_sec))

    _runtime_thread = threading.Thread(target=_runtime_loop, daemon=True)
    _runtime_thread.start()
    with _runtime_lock:
        return {"started": True, "status": _runtime_status}


@app.post("/api/runtime/stop")
async def runtime_stop():
    _runtime_stop_event.set()
    with _runtime_lock:
        _runtime_status["running"] = False
    return {"stopped": True, "status": _runtime_status}


@app.get("/api/runtime/status")
async def runtime_status():
    with _runtime_lock:
        return dict(_runtime_status)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _get_telegram_sender():
    """Telegram sender factory.

    - Default: RealTelegramSender()
    - Tests MUST monkeypatch this to InMemoryTelegramSender to avoid real network.
    """
    from notifications.telegram_sender import RealTelegramSender

    return RealTelegramSender()


@app.post("/api/telegram/test")
async def telegram_test(data: dict = {}):
    """Telegram test endpoint.

    Safety rules:
    - Dry-run by default
    - Requires confirm to attempt send
    - Tests must not perform real Telegram send; patch _get_telegram_sender.
    """
    confirm = data.get("confirm", "") if data else ""
    from notifications.telegram_event import TelegramEvent, TelegramEventType, NotificationSeverity

    event = TelegramEvent(
        event_type=TelegramEventType.SERVER_STARTED.value,
        title="🧪 SAT3 Telegram 알림 테스트",
        body="이 메시지는 SAT3 대시보드에서 전송된 테스트 알림입니다.",
        notification_severity=NotificationSeverity.NORMAL,
    )

    if confirm == "SEND_TEST_TELEGRAM":
        sender = _get_telegram_sender()
        result = sender.send(event)
        return {
            "sent": result.success,
            "message_id": result.message_id,
            "error": result.error_message,
            "preview": event.formatted_message,
        }

    return {
        "sent": False,
        "mode": "dry-run",
        "hint": "Send 'confirm': 'SEND_TEST_TELEGRAM' to actually send",
        "preview": event.formatted_message,
    }
