"""Dashboard API Routes — route handler functions

FastAPI app_factory가 없으므로 독립적인 handler 함수로 구현.
실제 FastAPI 연결 시 router에 등록.
"""
from __future__ import annotations
from typing import Any

from dashboard.dashboard_service import DashboardService
from dashboard.dashboard_snapshot import build_dashboard_summary
from dashboard.dashboard_models import (
    DashboardSummary,
    ScannerCandidateView,
    QuantScoreView,
    StrategySignalView,
    RiskDecisionView,
)

# Singleton service
_service = DashboardService()

# Last successful KIS account snapshot cache (to avoid transient API failures
# from wiping values to zeros on dashboard refresh)
_last_kis_account_snapshot: dict[str, Any] | None = None


def get_service() -> DashboardService:
    return _service


# ── Route Handlers ──

def _sync_dashboard_from_dry_result(dry: dict[str, Any]) -> None:
    svc = get_service()
    candidates = [
        ScannerCandidateView(
            symbol=str(c.get("symbol", "")),
            scanner_type=str(c.get("scanner_type", "")),
            included=bool(c.get("included", False)),
            excluded_reason=c.get("excluded_reason"),
            symbol_name=str(c.get("symbol_name", "")),
        )
        for c in (dry.get("candidates") or [])
    ]
    quant_scores = [
        QuantScoreView(
            symbol=str(s.get("symbol", "")),
            scanner_type=str(s.get("scanner_type", "")),
            decision=str(s.get("decision", "")),
            final_score=float(s.get("final_score", 0.0) or 0.0),
            liquidity_score=float(s.get("liquidity_score", 0.0) or 0.0),
            momentum_score=float(s.get("momentum_score", 0.0) or 0.0),
        )
        for s in (dry.get("scores") or [])
    ]
    signals = [
        StrategySignalView(
            signal_id=str(sig.get("signal_id", "")),
            symbol=str(sig.get("symbol", "")),
            side=str(sig.get("side", "")),
            strategy_type=str(sig.get("strategy_type", "")),
            confidence=float(sig.get("confidence", 0.0) or 0.0),
            market_regime=str(sig.get("market_regime", "UNKNOWN")),
        )
        for sig in (dry.get("signals") or [])
    ]
    risk_decisions = [
        RiskDecisionView(
            risk_decision_id=str(r.get("risk_decision_id", "")),
            symbol=str(r.get("symbol", "")),
            side=str(r.get("side", "")),
            allowed=bool(r.get("allowed", False)),
            reason_code=str(r.get("reason_code", "")),
            reason_text=str(r.get("reason_text", "")),
        )
        for r in (dry.get("risk_decisions") or [])
    ]

    svc.inject_candidates(candidates)
    svc.inject_quant_scores(quant_scores)
    svc.inject_strategy_signals(signals)
    svc.inject_risk_decisions(risk_decisions)


def run_runtime_tick_and_sync(mode: str = "dry-run", session: str = "REGULAR_MARKET") -> dict[str, Any]:
    from runtime.orchestrator import Orchestrator
    from runtime.scheduler import SessionState

    orch = Orchestrator()
    session_enum = SessionState[session] if session in SessionState.__members__ else SessionState.UNKNOWN
    tick = orch.tick(session_enum, mode=mode)
    dry = tick.get("dry_run") or {}
    if dry:
        _sync_dashboard_from_dry_result(dry)
    return tick


def handle_get_summary() -> dict[str, Any]:
    svc = get_service()

    try:
        run_runtime_tick_and_sync(mode="dry-run", session="REGULAR_MARKET")
    except Exception:
        pass

    system = svc.get_system_status()
    summary = build_dashboard_summary(
        live_trading_enabled=system.live_trading_enabled,
        emergency_stop=system.emergency_stop,
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
    """Live timeline list.

    Returns fields required by SAT3-AUDIT-LIVE-TIMELINE spec.
    """
    items: list[dict[str, Any]] = []
    for e in get_service().get_audit_timeline(limit):
        # AuditTimelineView -> response dict
        items.append({
            "event_id": e.event_id,
            "event_time": e.timestamp,
            "event_type": e.event_type,
            "severity": e.severity,
            "source": e.source,
            "symbol": e.symbol,
            "strategy_name": e.strategy_name,
            "status": e.status,
            "summary": e.summary,
            "correlation_id": e.correlation_id,
            "has_checklist": bool(getattr(e, "has_checklist", False)),
        })
    return items


def handle_get_audit_by_correlation(correlation_id: str) -> list[dict[str, Any]]:
    return [_to_dict(e)
            for e in get_service().get_audit_by_correlation(correlation_id)]


def handle_get_audit_event_detail(event_id: str) -> dict[str, Any]:
    detail = get_service().get_audit_event_detail(event_id)
    # In repository mode, not_found returns {error: not_found}
    if isinstance(detail, dict) and detail.get("error") == "not_found":
        return detail
    return detail


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

    global _last_kis_account_snapshot

    acc = os.getenv("KIS_ACCOUNT_NO", "")
    prod = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "01")
    app_key = os.getenv("KIS_APP_KEY", "")
    app_secret = os.getenv("KIS_APP_SECRET", "")

    if not acc or not app_key or not app_secret:
        return _to_dict(KisAccountView(
            account_no=acc, product_code=prod, stale=True,
        ))

    def _as_int(v: Any) -> int:
        try:
            s = str(v or "0").replace(",", "").strip()
            return int(float(s)) if s else 0
        except Exception:
            return 0

    try:
        # 1) Get access token
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
            if _last_kis_account_snapshot is not None:
                cached = dict(_last_kis_account_snapshot)
                cached["stale"] = True
                return cached
            return _to_dict(KisAccountView(account_no=acc, product_code=prod, stale=True))

        # 2) Balance inquiry
        bal_url = (
            "https://openapi.koreainvestment.com:9443"
            "/uapi/domestic-stock/v1/trading/inquire-balance"
            "?CANO=" + acc.replace("-", "")[:8] +
            "&ACNT_PRDT_CD=" + prod +
            "&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01"
            "&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N"
            "&PRCS_DVSN=00&CTX_AREA_FK100=&CTX_AREA_NK100="
        )
        bal_req = urllib.request.Request(bal_url, method="GET")
        bal_req.add_header("authorization", f"Bearer {access_token}")
        bal_req.add_header("appkey", app_key)
        bal_req.add_header("appsecret", app_secret)
        bal_req.add_header("tr_id", "TTTC8434R")
        bal_resp = urllib.request.urlopen(bal_req, timeout=10)
        bal_data = json.loads(bal_resp.read().decode())

        if bal_data.get("rt_cd") == "0":
            # KIS balance schema:
            # - output1: holdings list (종목별)
            # - output2: account summary (예수금/평가금액/매수금액 등)
            out1_raw = bal_data.get("output1", [])
            out2_raw = bal_data.get("output2", [])

            holdings = len(out1_raw) if isinstance(out1_raw, list) else 0

            summary = {}
            if isinstance(out2_raw, list) and len(out2_raw) > 0 and isinstance(out2_raw[0], dict):
                summary = out2_raw[0]
            elif isinstance(out2_raw, dict):
                summary = out2_raw

            # Summary keys can vary across environments/messages; keep fallbacks.
            deposit = _as_int(summary.get("dnca_tot_amt") or summary.get("dnca_tot_amt1") or summary.get("dnca_tot_amt_1"))
            total_value = _as_int(summary.get("tot_evlu_amt") or summary.get("tot_evlu_amt2") or summary.get("tot_evlu_amt_2"))
            buy_amount = _as_int(summary.get("pchs_amt") or summary.get("scts_pchs_amt") or summary.get("tot_pchs_amt"))
            d2 = _as_int(summary.get("d2_auto_rdpt_amt") or summary.get("nxdy_excc_amt") or summary.get("prvs_rcdl_excc_amt"))

            view = _to_dict(KisAccountView(
                account_no=acc,
                product_code=prod,
                deposit=deposit,
                total_value=total_value,
                total_buy_amount=buy_amount,
                holding_count=holdings,
                d2_deposit=d2,
                stale=False,
            ))
            _last_kis_account_snapshot = dict(view)
            return view

        # API-level failure: return last known good snapshot as stale if available.
        if _last_kis_account_snapshot is not None:
            cached = dict(_last_kis_account_snapshot)
            cached["stale"] = True
            return cached

        return _to_dict(KisAccountView(account_no=acc, product_code=prod, stale=True))

    except Exception:
        # Network/auth transient failure: preserve last good values instead of replacing with zeros.
        if _last_kis_account_snapshot is not None:
            cached = dict(_last_kis_account_snapshot)
            cached["stale"] = True
            return cached

        return _to_dict(KisAccountView(
            account_no=acc,
            product_code=prod,
            stale=True,
            deposit=-1,  # -1 = error marker (no prior snapshot)
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
