"""Dashboard API Routes — route handler functions

FastAPI app_factory가 없으므로 독립적인 handler 함수로 구현.
실제 FastAPI 연결 시 router에 등록.
"""
from __future__ import annotations
from typing import Any

from dashboard.dashboard_service import DashboardService
from dashboard.dashboard_snapshot import build_dashboard_summary
from dashboard.dashboard_models import DashboardSummary

# Singleton service
_service = DashboardService()


def get_service() -> DashboardService:
    return _service


# ── Route Handlers ──

def handle_get_summary() -> dict[str, Any]:
    svc = get_service()
    summary = build_dashboard_summary(
        live_trading_enabled=False,
        emergency_stop=False,
        session_state="REGULAR_MARKET",
        market_regime="BULL",
        allow_new_buy=True,
        scanner_candidates=svc.get_candidates(),
        quant_scores=svc.get_quant_scores(),
        strategy_signals=svc.get_strategy_signals(),
        risk_decisions=svc.get_risk_decisions(),
        orders=svc.get_orders(),
        fills=svc.get_fills(),
    )
    return _to_dict(summary)


def handle_get_system() -> dict[str, Any]:
    return _to_dict(get_service().get_system_status())


def handle_get_session() -> dict[str, Any]:
    return _to_dict(get_service().get_session_status())


def handle_get_market_regime() -> dict[str, Any]:
    return _to_dict(get_service().get_market_regime())


def handle_get_candidates() -> list[dict[str, Any]]:
    return [_to_dict(c) for c in get_service().get_candidates()]


def handle_get_quant_scores() -> list[dict[str, Any]]:
    return [_to_dict(s) for s in get_service().get_quant_scores()]


def handle_get_strategy_signals() -> list[dict[str, Any]]:
    return [_to_dict(s) for s in get_service().get_strategy_signals()]


def handle_get_risk_decisions() -> list[dict[str, Any]]:
    return [_to_dict(r) for r in get_service().get_risk_decisions()]


def handle_get_orders() -> list[dict[str, Any]]:
    return [_to_dict(o) for o in get_service().get_orders()]


def handle_get_fills() -> list[dict[str, Any]]:
    return [_to_dict(f) for f in get_service().get_fills()]


def handle_get_portfolio() -> list[dict[str, Any]]:
    return [_to_dict(p) for p in get_service().get_portfolio()]


def handle_get_eod_latest() -> dict[str, Any] | None:
    eod = get_service().get_eod_latest()
    return _to_dict(eod) if eod else {"message": "No EOD report yet"}


def handle_get_audit_timeline(limit: int = 50) -> list[dict[str, Any]]:
    return [_to_dict(e) for e in get_service().get_audit_timeline(limit)]


def handle_get_audit_by_correlation(correlation_id: str) -> list[dict[str, Any]]:
    return [_to_dict(e)
            for e in get_service().get_audit_by_correlation(correlation_id)]


def handle_get_telegram_status() -> dict[str, Any]:
    from dashboard.dashboard_models import TelegramStatusView
    import os
    try:
        import urllib.request, json
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return _to_dict(TelegramStatusView(connected=False, error="TELEGRAM_BOT_TOKEN not set"))
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        if data.get("ok"):
            bot = data["result"]
            return _to_dict(TelegramStatusView(
                connected=True,
                bot_name=f"@{bot.get('username', 'unknown')}",
                chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
                last_message_at="online",
            ))
        return _to_dict(TelegramStatusView(connected=False, error=str(data)))
    except Exception as e:
        return _to_dict(TelegramStatusView(connected=False, error=str(e)))


def handle_get_kis_account() -> dict[str, Any]:
    from dashboard.dashboard_models import KisAccountView
    import os, json, urllib.request, urllib.error
    acc = os.getenv("KIS_ACCOUNT_NO", "")
    prod = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "01")
    app_key = os.getenv("KIS_APP_KEY", "")
    app_secret = os.getenv("KIS_APP_SECRET", "")

    if not acc or not app_key or not app_secret:
        return _to_dict(KisAccountView(
            account_no=acc, product_code=prod, stale=True,
        ))

    try:
        # 1. Get access token
        token_url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
        token_body = json.dumps({
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        }).encode()
        token_req = urllib.request.Request(token_url, data=token_body, method="POST")
        token_req.add_header("content-type", "application/json")
        token_resp = urllib.request.urlopen(token_req, timeout=10)
        token_data = json.loads(token_resp.read().decode())
        access_token = token_data.get("access_token", "")

        if not access_token:
            return _to_dict(KisAccountView(account_no=acc, product_code=prod, stale=True))

        # 2. Balance inquiry
        bal_url = ("https://openapi.koreainvestment.com:9443"
                   "/uapi/domestic-stock/v1/trading/inquire-balance"
                   "?CANO=" + acc.replace("-", "")[:8] +
                   "&ACNT_PRDT_CD=" + prod +
                   "&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01"
                   "&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N"
                   "&PRCS_DVSN=00&CTX_AREA_FK100=&CTX_AREA_NK100=")
        bal_req = urllib.request.Request(bal_url, method="GET")
        bal_req.add_header("authorization", f"Bearer {access_token}")
        bal_req.add_header("appkey", app_key)
        bal_req.add_header("appsecret", app_secret)
        bal_req.add_header("tr_id", "TTTC8434R")
        bal_resp = urllib.request.urlopen(bal_req, timeout=10)
        bal_data = json.loads(bal_resp.read().decode())

        if bal_data.get("rt_cd") == "0" and "output1" in bal_data:
            out1 = bal_data["output1"]
            deposit = int(out1.get("dnca_tot_amt", "0") or "0")
            total_value = int(out1.get("tot_evlu_amt", "0") or "0")
            buy_amount = int(out1.get("pchs_amt", "0") or "0")

            # Count holdings from output2
            holdings = 0
            if "output2" in bal_data and isinstance(bal_data["output2"], list):
                holdings = len(bal_data["output2"])

            return _to_dict(KisAccountView(
                account_no=acc,
                product_code=prod,
                deposit=deposit,
                total_value=total_value,
                total_buy_amount=buy_amount,
                holding_count=holdings,
                d2_deposit=int(out1.get("d2_auto_rdpt_amt", "0") or "0"),
                stale=False,
            ))

        return _to_dict(KisAccountView(
            account_no=acc, product_code=prod, stale=True,
        ))

    except Exception as e:
        return _to_dict(KisAccountView(
            account_no=acc, product_code=prod, stale=True,
        ))


def handle_get_daily_summary(date_str: str = "") -> dict[str, Any]:
    from dashboard.dashboard_models import DailySummaryView
    from datetime import date
    d = date_str or date.today().isoformat()
    return _to_dict(DailySummaryView(date=d))


def handle_get_strategy_breakdown(date_str: str = "") -> list[dict[str, Any]]:
    return []


def handle_get_logs(date_str: str = "", category: str = "system",
                    max_lines: int = 100) -> dict[str, Any]:
    from tools.daily_logger import DailyLogger, LogCategory
    from dashboard.dashboard_models import LogEntryView
    from datetime import date
    logger = DailyLogger()
    d = date_str or date.today().isoformat()
    cat = LogCategory(category) if category in [c.value for c in LogCategory] else LogCategory.SYSTEM
    lines = logger.get_logs(d, cat, max_lines=max_lines)
    return _to_dict(LogEntryView(
        date=d, category=cat.value, lines=lines,
        available_dates=logger.get_available_dates(),
        available_categories=logger.get_available_categories(d),
    ))


def handle_get_log_dates() -> list[str]:
    from tools.daily_logger import DailyLogger
    return DailyLogger().get_available_dates()


# ── Helper ──

def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        return {f: getattr(obj, f) for f in obj.__dataclass_fields__}
    return dict(obj) if isinstance(obj, dict) else {"value": str(obj)}
