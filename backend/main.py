"""SAT3 Backend FastAPI Application.

Entry point for uvicorn: uvicorn main:app --host 127.0.0.1 --port 8000
"""
import os
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

app = FastAPI(title="SAT3 Dashboard API", version="3.0.0")

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
    allow_methods=["GET"],
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
    from dashboard.dashboard_routes import handle_get_system
    return {"connection_state": "DISCONNECTED", "subscribed_channels": []}


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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/telegram/test")
async def telegram_test(data: dict = {}):
    """Telegram test endpoint. Dry-run by default, requires confirm to actually send."""
    confirm = data.get("confirm", "") if data else ""
    from notifications.telegram_event import TelegramEvent, TelegramEventType, NotificationSeverity
    from notifications.telegram_sender import RealTelegramSender

    event = TelegramEvent(
        event_type=TelegramEventType.SERVER_STARTED.value,
        title="🧪 SAT3 Telegram 알림 테스트",
        body="이 메시지는 SAT3 대시보드에서 전송된 테스트 알림입니다.",
        notification_severity=NotificationSeverity.NORMAL,
    )

    if confirm == "SEND_TEST_TELEGRAM":
        sender = RealTelegramSender()
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
