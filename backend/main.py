"""SAT3 Backend FastAPI Application.

Entry point for uvicorn: uvicorn main:app --host 127.0.0.1 --port 8000
"""
import json
import os
import re
import sqlite3
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
    "live_start_block_reasons": [],
    "last_order_status": "",
    "order_submit_enabled": False,
    "order_submit_enabled_reason": "",
    "order_submit_checks": {},
}


def _read_emergency_stop_active() -> bool:
    try:
        p = Path(__file__).resolve().parents[1] / ".emergency_stop"
        if not p.exists():
            return False
        t = p.read_text(encoding="utf-8", errors="replace")
        return "active" in t.lower()
    except Exception:
        return False


def _is_set(name: str) -> bool:
    return os.getenv(name, "").strip() != ""


def _risk_limits_loaded() -> tuple[bool, list[str]]:
    def _parse_pos_int(name: str) -> tuple[bool, int | None]:
        raw = os.getenv(name, "").strip()
        if not raw:
            return False, None
        try:
            v = int(raw)
        except Exception:
            return False, None
        return (v > 0), (v if v > 0 else None)

    ok_daily, _ = _parse_pos_int("SAT3_MAX_DAILY_LOSS_KRW")
    ok_pos, _ = _parse_pos_int("SAT3_MAX_POSITION_COUNT")
    ok_order_amt, _ = _parse_pos_int("SAT3_MAX_ORDER_AMOUNT_KRW")
    ok_symbol_amt, _ = _parse_pos_int("SAT3_MAX_AMOUNT_PER_SYMBOL_KRW")
    ok_pending, _ = _parse_pos_int("SAT3_MAX_PENDING_ORDERS")

    dup_raw = os.getenv("SAT3_DUPLICATE_ORDER_GUARD_ENABLED", "").strip().lower()
    ok_dup = dup_raw in {"true", "false", "1", "0", "yes", "no", "on", "off"}

    required = {
        "SAT3_MAX_DAILY_LOSS_KRW": ok_daily,
        "SAT3_MAX_POSITION_COUNT": ok_pos,
        "SAT3_MAX_ORDER_AMOUNT_KRW": ok_order_amt,
        "SAT3_MAX_AMOUNT_PER_SYMBOL_KRW": ok_symbol_amt,
        "SAT3_MAX_PENDING_ORDERS": ok_pending,
        "SAT3_DUPLICATE_ORDER_GUARD_ENABLED": ok_dup,
    }
    missing_or_invalid = [k for k, ok in required.items() if not ok]
    return len(missing_or_invalid) == 0, missing_or_invalid


def _get_telegram_target_readiness() -> tuple[bool, dict[str, object]]:
    """Readiness check for Telegram target validity without network calls.

    정책:
    - 단순 토큰/chat_id 존재만으로는 통과시키지 않음
    - explicit target 설정 + 최근 성공 이력 플래그가 있어야 TELEGRAM_TARGET_VALID 통과
    - 실제 전송/외부 호출은 수행하지 않음
    """
    has_token = bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    has_chat_id = bool(os.getenv("TELEGRAM_CHAT_ID", "").strip())
    has_base_credentials = has_token and has_chat_id

    explicit_target = os.getenv("SAT3_TELEGRAM_EXPLICIT_TARGET", "").strip()
    explicit_ok_raw = os.getenv("SAT3_TELEGRAM_EXPLICIT_TARGET_OK", "").strip().lower()
    explicit_ok = explicit_ok_raw in {"1", "true", "yes", "on"}

    default_ok_raw = os.getenv("SAT3_TELEGRAM_DEFAULT_TARGET_OK", "").strip().lower()
    default_ok = default_ok_raw in {"1", "true", "yes", "on"}

    target_valid = bool(has_base_credentials and explicit_target and explicit_ok)
    reason = "explicit_target_verified" if target_valid else "explicit_target_not_verified"

    return target_valid, {
        "telegram_base_credentials": has_base_credentials,
        "telegram_default_target_ok": default_ok,
        "telegram_explicit_target": explicit_target,
        "telegram_explicit_target_ok": explicit_ok,
        "telegram_target_reason": reason,
    }


def _safe_load_json_dict(path: Path) -> dict[str, object] | None:
    try:
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _artifact_int(value: object, default: int = 0) -> int:
    try:
        if value is None:
            return default
        raw = str(value).replace(",", "").strip()
        return int(float(raw or default))
    except Exception:
        return default


def _artifact_bool(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _parse_submit_artifact(path: Path) -> dict[str, object] | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None

    kv: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        kv[key.strip()] = value.strip()

    status = str(kv.get("status", "") or "").upper()
    if status != "SUBMITTED":
        return None

    order_number = str(kv.get("order_number", "") or "")
    symbol = ""
    m = re.search(r"live_pilot_submit_once_\d{8}_(\d{6})_", path.name)
    if m:
        symbol = m.group(1)

    return {
        "path": str(path),
        "mtime": path.stat().st_mtime if path.exists() else 0.0,
        "status": status,
        "order_number": order_number,
        "symbol": symbol,
        "filled_qty": _artifact_int(kv.get("filled_qty", 0), 0),
        "remaining_qty": _artifact_int(kv.get("remaining_qty", 1), 1),
    }


def _parse_reconciliation_artifact(data: dict[str, object], *, order_number: str = "", symbol: str = "") -> dict[str, object] | None:
    artifact_order = str(
        data.get("order_no") or data.get("order_number") or data.get("target_order_no") or ""
    ).strip()
    artifact_symbol = str(data.get("symbol") or "").strip()
    if order_number and artifact_order and artifact_order != order_number:
        return None
    if symbol and artifact_symbol and artifact_symbol != symbol:
        return None

    before = data.get("before") if isinstance(data.get("before"), dict) else {}
    after = data.get("after") if isinstance(data.get("after"), dict) else {}
    cancel = data.get("cancel") if isinstance(data.get("cancel"), dict) else {}

    after_status = str(after.get("status") or data.get("status") or before.get("status") or "").upper()
    before_status = str(before.get("status") or "").upper()
    status = after_status or before_status or str(data.get("status_field") or "").upper()

    after_open = after.get("open")
    open_flag = _artifact_bool(after_open if after_open is not None else data.get("open"))
    remaining_qty = _artifact_int(after.get("remaining_qty", data.get("remaining_qty", before.get("remaining_qty", 0))), 0)
    filled_qty = _artifact_int(after.get("filled_qty", data.get("filled_qty", before.get("filled_qty", 0))), 0)
    blocker_cleared = _artifact_bool(data.get("blocker_cleared"))
    cancel_attempted = _artifact_bool(cancel.get("attempted"))
    has_definitive_closed = blocker_cleared or (
        status in {"NOT_FOUND", "CANCELED", "CANCELLED", "FILLED", "FILL_CONFIRMED", "CLOSED", "REJECTED", "FAILED", "ERROR"}
        and remaining_qty == 0
        and not open_flag
    )

    if has_definitive_closed:
        return {
            "open": False,
            "known": True,
            "source": "reconciliation",
            "status": status or "NOT_FOUND",
            "order_number": artifact_order,
            "symbol": artifact_symbol,
            "filled_qty": filled_qty,
            "remaining_qty": remaining_qty,
            "reason": "RECONCILED_BY_READONLY",
            "blocker": "",
            "cancel_attempted": cancel_attempted,
        }

    if status or artifact_order or artifact_symbol or blocker_cleared or cancel_attempted:
        if open_flag or remaining_qty > 0:
            return {
                "open": True,
                "known": True,
                "source": "reconciliation",
                "status": status or "OPEN",
                "order_number": artifact_order,
                "symbol": artifact_symbol,
                "filled_qty": filled_qty,
                "remaining_qty": remaining_qty,
                "reason": "READONLY_OPEN_ORDER",
                "blocker": "OPEN_ORDER_PENDING",
                "cancel_attempted": cancel_attempted,
            }

        return {
            "open": False,
            "known": False,
            "source": "reconciliation",
            "status": status or "UNKNOWN",
            "order_number": artifact_order,
            "symbol": artifact_symbol,
            "filled_qty": filled_qty,
            "remaining_qty": remaining_qty,
            "reason": "READONLY_UNAVAILABLE",
            "blocker": "READONLY_UNAVAILABLE",
            "cancel_attempted": cancel_attempted,
        }

    return None


def _latest_submit_evidence(project_root: Path) -> dict[str, object] | None:
    logs_dir = project_root / "logs"
    try:
        candidates = sorted(
            logs_dir.glob("live_pilot_submit_once_*_LIVE_PILOT_ONCE_final.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        candidates = []

    for final_path in candidates:
        parsed = _parse_submit_artifact(final_path)
        if parsed is not None:
            return parsed
    return None


def _latest_reconciliation_evidence(project_root: Path, *, order_number: str = "", symbol: str = "", not_before: float = 0.0) -> dict[str, object] | None:
    logs_dir = project_root / "logs"
    try:
        candidates = sorted(
            logs_dir.glob("order_cancel_*_final.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        candidates = []

    for path in candidates:
        try:
            mtime = path.stat().st_mtime
        except Exception:
            continue
        if not_before and mtime < not_before:
            continue
        data = _safe_load_json_dict(path)
        if not data:
            continue
        parsed = _parse_reconciliation_artifact(data, order_number=order_number, symbol=symbol)
        if parsed is None:
            continue
        parsed["path"] = str(path)
        parsed["mtime"] = mtime
        return parsed
    return None


def _live_pilot_open_order_state(project_root: Path) -> dict[str, object]:
    """Detect whether the submit-once pilot still has an open/pending order.

    Priority:
    1) latest reconciliation artifact (read-only / cancel-check)
    2) audit DB LIVE_PILOT_ONCE rows
    3) submit artifact fallback
    4) fail-closed when no definitive evidence exists
    """
    submit_evidence = _latest_submit_evidence(project_root)
    submit_mtime = float(submit_evidence.get("mtime", 0.0) or 0.0) if submit_evidence else 0.0
    target_order_number = str(submit_evidence.get("order_number", "") or "") if submit_evidence else ""
    target_symbol = str(submit_evidence.get("symbol", "") or "") if submit_evidence else ""

    db_path = project_root / "data" / "sat3_audit.db"
    conn = None
    audit_pending_state = None
    if db_path.is_file():
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT event_type, status, summary, payload, correlation_id, symbol, source, event_time, created_at "
                "FROM audit_events WHERE source = ? ORDER BY COALESCE(event_time, created_at) DESC, id DESC LIMIT 100",
                ("LIVE_PILOT_ONCE",),
            ).fetchall()
            for row in rows:
                payload_raw = row["payload"] or "{}"
                payload = json.loads(payload_raw) if isinstance(payload_raw, str) else dict(payload_raw or {})
                status = str(payload.get("status") or row["status"] or "").upper()
                remaining_qty = _artifact_int(payload.get("remaining_qty", 0), 0)
                filled_qty = _artifact_int(payload.get("filled_qty", 0), 0)
                order_number = str(payload.get("order_number") or "")
                symbol = str(payload.get("symbol") or row["symbol"] or "")
                if status == "SUBMITTED" and remaining_qty > 0:
                    target_order_number = target_order_number or order_number
                    target_symbol = target_symbol or symbol
                    audit_pending_state = {
                        "open": True,
                        "known": True,
                        "source": "audit_db",
                        "status": status,
                        "order_number": order_number,
                        "symbol": symbol,
                        "filled_qty": filled_qty,
                        "remaining_qty": remaining_qty,
                        "reason": "LIVE_PILOT_ONCE_ORDER_PENDING",
                        "blocker": "OPEN_ORDER_PENDING",
                    }
                    break
                if status in {"FILL_CONFIRMED", "FILLED", "CANCELLED", "CANCELED", "REJECTED", "FAILED", "ERROR"}:
                    return {
                        "open": False,
                        "known": True,
                        "source": "audit_db",
                        "status": status,
                        "order_number": order_number,
                        "symbol": symbol,
                        "filled_qty": filled_qty,
                        "remaining_qty": remaining_qty,
                        "reason": status,
                        "blocker": "",
                    }
        except Exception:
            pass
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    reconciliation = _latest_reconciliation_evidence(
        project_root,
        order_number=target_order_number,
        symbol=target_symbol,
        not_before=submit_mtime,
    )
    if reconciliation is not None:
        return reconciliation

    if audit_pending_state is not None:
        return audit_pending_state

    if submit_evidence is not None:
        return {
            "open": True,
            "known": True,
            "source": "logs",
            "status": "SUBMITTED",
            "order_number": target_order_number,
            "symbol": target_symbol,
            "filled_qty": _artifact_int(submit_evidence.get("filled_qty", 0), 0),
            "remaining_qty": max(1, _artifact_int(submit_evidence.get("remaining_qty", 1), 1)),
            "reason": "LIVE_PILOT_ONCE_LOG_PENDING",
            "blocker": "OPEN_ORDER_PENDING",
        }

    return {
        "open": False,
        "known": False,
        "source": "none",
        "status": "",
        "order_number": "",
        "symbol": "",
        "filled_qty": 0,
        "remaining_qty": 0,
        "reason": "READONLY_UNAVAILABLE",
        "blocker": "READONLY_UNAVAILABLE",
    }


def _build_live_start_checks(refresh_snapshots: bool = True) -> tuple[dict[str, bool], dict[str, object]]:
    from dashboard.dashboard_routes import get_service, handle_get_summary, trigger_snapshot_refresh_for_precheck

    svc = get_service()
    if refresh_snapshots:
        refresh_status = trigger_snapshot_refresh_for_precheck(mode="live", session="REGULAR_MARKET")
    else:
        refresh_status = {"enabled": False, "reason": "read_only_summary_no_refresh"}
    summary = handle_get_summary(include_live_auto_ready=False)

    # Reuse values already computed during summary build to avoid duplicate KIS probes
    # in the same precheck cycle (token-rate sensitive path).
    system = svc.get_system_status()
    session = summary.get("session")
    regime = summary.get("market_regime")
    router = summary.get("data_router") or {}
    ws = summary.get("ws_status") or {}

    session_state = getattr(session, "session_state", "UNKNOWN") if session is not None else "UNKNOWN"
    session_reason = getattr(session, "reason", None) if session is not None else None
    session_source = None
    if isinstance(session_reason, str) and "=" in session_reason:
        session_source = session_reason.split("=", 1)[1]

    regime_name = getattr(regime, "regime", "UNKNOWN") if regime is not None else "UNKNOWN"
    regime_reason = getattr(regime, "reason", None) if regime is not None else None
    regime_source = None
    if isinstance(regime_reason, str) and "=" in regime_reason:
        regime_source = regime_reason.split("=", 1)[1]

    risk_loaded, risk_missing = _risk_limits_loaded()
    telegram_target_valid, telegram_ctx = _get_telegram_target_readiness()
    open_order_state = _live_pilot_open_order_state(Path(__file__).resolve().parents[1])

    open_order_blocker = str(open_order_state.get("blocker", "") or "").strip()
    open_order_pending = bool(open_order_state.get("known", False)) and (
        bool(open_order_state.get("open", False)) or open_order_blocker == "OPEN_ORDER_PENDING"
    )

    checks = {
        "LIVE_TRADING_ENABLED_TRUE": bool(system.live_trading_enabled),
        "CONFIRM_ENV_SET": os.getenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", "") == "CONFIRM_LIVE_AUTO_TRADING",
        "EMERGENCY_STOP_INACTIVE": not _read_emergency_stop_active(),
        "KIS_REST_AVAILABLE": bool(router.get("rest_available", False)),
        "KIS_REST_FRESH": bool(router.get("rest_snapshot_fresh", False)),
        "KIS_WS_AVAILABLE": ws.get("connection_state") == "CONNECTED" or bool(ws.get("snapshot_fresh", False)),
        "KIS_WS_FRESH": bool(ws.get("snapshot_fresh", False)),
        "SESSION_REGULAR_MARKET": session_state == "REGULAR_MARKET",
        "MARKET_REGIME_KNOWN": regime_name != "UNKNOWN",
        "PORTFOLIO_SOURCE_KIS_REST_FRESH": (not bool(summary.get("portfolio_stale", False))) and str(summary.get("portfolio_source_of_truth", "KIS_REST")) == "KIS_REST",
        "RISK_LIMITS_LOADED": risk_loaded,
        "TELEGRAM_TARGET_VALID": telegram_target_valid,
        "OPEN_ORDER_RECONCILIATION_KNOWN": bool(open_order_state.get("known", False)),
        # True when no open order is blocking readiness.
        "OPEN_ORDER_PENDING": not open_order_pending,
        "AUDIT_LOGGING_ACTIVE": bool("_audit_repo" in globals()),
        "FILL_RECONCILIATION_ACTIVE": True,
    }
    context = {
        "session": session_state,
        "session_reason": session_reason,
        "session_source": session_source,
        "market_regime": regime_name,
        "market_regime_reason": regime_reason,
        "market_regime_source": regime_source,
        "rest_available": bool(router.get("rest_available", False)),
        "rest_snapshot_fresh": bool(router.get("rest_snapshot_fresh", False)),
        "ws_state": ws.get("connection_state", "UNKNOWN"),
        "ws_snapshot_fresh": bool(ws.get("snapshot_fresh", False)),
        "ws_status_reason": ws.get("status_reason", ""),
        "risk_limits_missing": risk_missing,
        "portfolio_stale": summary.get("portfolio_stale"),
        "open_order_state": open_order_state,
        "open_order_blocker": open_order_state.get("blocker", ""),
        "open_order_known": bool(open_order_state.get("known", False)),
        "snapshot_refresh": refresh_status,
        **telegram_ctx,
    }
    return checks, context


def _count_today_submitted_orders(project_root: Path, symbol: str = "") -> int:
    db_path = project_root / "data" / "sat3_audit.db"
    if not db_path.is_file():
        return 0
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(db_path))
        params: list[object] = ["SUBMITTED"]
        sql = "SELECT COUNT(*) AS cnt FROM orders WHERE UPPER(COALESCE(status, '')) = ? AND date(created_at) = date('now')"
        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)
        row = conn.execute(sql, params).fetchone()
        if row is None:
            return 0
        return int(row[0] or 0)
    except Exception:
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _get_selected_live_candidate(live_real_pipeline_data: dict[str, object] | None, live_pipeline: dict[str, object] | None) -> dict[str, object] | None:
    candidates: list[dict[str, object]] = []
    if isinstance(live_real_pipeline_data, dict):
        raw = live_real_pipeline_data.get("candidates") or []
        if isinstance(raw, list):
            candidates.extend([c for c in raw if isinstance(c, dict)])
    if not candidates and isinstance(live_pipeline, dict):
        raw = live_pipeline.get("scanner_candidates_sample") or []
        if isinstance(raw, list):
            candidates.extend([c for c in raw if isinstance(c, dict)])
    return candidates[0] if candidates else None


def _build_live_order_submit_state(
    *,
    checks: dict[str, bool],
    context: dict[str, object],
    live_pipeline: dict[str, object] | None,
    live_real_pipeline_data: dict[str, object] | None,
    allow_new_buy: bool,
    project_root: Path,
) -> dict[str, object]:
    from dashboard.dashboard_routes import handle_get_kis_account
    from kis.token_cache import TokenCache

    live_pipeline = live_pipeline or {}
    context = context or {}
    open_order_raw = context.get("open_order_state")
    open_order_state = open_order_raw if isinstance(open_order_raw, dict) else {}
    open_order_known = bool(open_order_state.get("known", False))
    open_order_pending = bool(open_order_state.get("open", False)) if open_order_known else False

    token_cache = TokenCache()
    token_record = token_cache.load()
    token_known = token_record is not None
    token_expired = True
    token_reason = "TOKEN_CACHE_UNAVAILABLE"
    if token_known:
        try:
            token_expired = bool(token_cache.is_expired(token_record))
            token_reason = "TOKEN_EXPIRED" if token_expired else "TOKEN_VALID"
        except Exception:
            token_expired = True
            token_reason = "TOKEN_CACHE_ERROR"

    def _to_int(value: object, default: int = 0) -> int:
        try:
            raw = str(value).replace(",", "").strip()
            return int(float(raw)) if raw else default
        except Exception:
            return default

    try:
        account_view = handle_get_kis_account()
        if isinstance(account_view, dict):
            account_no_raw = str(account_view.get("account_no", "") or "")
            product_code_raw = str(account_view.get("product_code", "") or "")
            if "-" in account_no_raw:
                account_no_part, product_code_part = account_no_raw.split("-", 1)
                account_parts_ok = bool(
                    re.fullmatch(r"\d{8}", account_no_part.strip())
                    and re.fullmatch(r"\d{2}", (product_code_part or product_code_raw).strip())
                )
            else:
                account_parts_ok = bool(
                    re.fullmatch(r"\d{8}", account_no_raw.strip())
                    and re.fullmatch(r"\d{2}", product_code_raw.strip())
                )
            balance_ok = not bool(account_view.get("stale", True))
            total_buyable = _to_int(account_view.get("deposit", 0), 0)
            orderable_ok = balance_ok and total_buyable > 0
            cash_ok = orderable_ok
            balance = {
                "data_available": balance_ok,
                "total_buyable": total_buyable,
                "source": "KIS_API",
            }
        else:
            account_parts_ok = False
            balance = {"data_available": False, "total_buyable": 0}
    except Exception:
        account_parts_ok = False
        balance = {"data_available": False, "total_buyable": 0}
    balance_ok = bool(balance.get("data_available", False))
    total_buyable = _to_int(balance.get("total_buyable", 0), 0)
    orderable_ok = balance_ok and total_buyable > 0
    cash_ok = orderable_ok

    selected_candidate = _get_selected_live_candidate(live_real_pipeline_data, live_pipeline)
    selected_row = selected_candidate if isinstance(selected_candidate, dict) else {}
    selected_symbol = str(selected_row.get("symbol", "") or "")
    candidate_metrics_raw = selected_row.get("metrics") if isinstance(selected_row.get("metrics"), dict) else {}
    candidate_metrics = candidate_metrics_raw if isinstance(candidate_metrics_raw, dict) else {}
    selected_product_type = str(selected_row.get("product_type") or candidate_metrics.get("product_type") or "").upper()

    readiness_pipeline = live_real_pipeline_data if isinstance(live_real_pipeline_data, dict) else live_pipeline

    def _list_rows(source: dict[str, object], *keys: str) -> list[dict[str, object]]:
        for key in keys:
            raw = source.get(key)
            if isinstance(raw, list):
                return [item for item in raw if isinstance(item, dict)]
        return []

    readiness_signals = _list_rows(readiness_pipeline, "signals", "strategy_signals_sample")
    readiness_risk = _list_rows(readiness_pipeline, "risk_decisions", "risk_decisions_sample")
    strategy_buy = any(str(sig.get("side", "")).upper() == "BUY" for sig in readiness_signals)
    risk_allowed = any(bool(r.get("allowed", False)) for r in readiness_risk) and not any(not bool(r.get("allowed", False)) for r in readiness_risk)
    audit_ready = bool(checks.get("AUDIT_LOGGING_ACTIVE", False))

    submitted_today = _count_today_submitted_orders(project_root)
    daily_limit_raw = os.getenv("SAT3_MAX_DAILY_ORDER_COUNT", os.getenv("SAT3_MAX_DAILY_ORDERS", "1")).strip()
    try:
        daily_limit = max(1, int(daily_limit_raw))
    except Exception:
        daily_limit = 1
    duplicate_guard_raw = os.getenv("SAT3_DUPLICATE_ORDER_GUARD_ENABLED", "true").strip().lower()
    duplicate_guard_enabled = duplicate_guard_raw in {"1", "true", "yes", "on", "y"}
    duplicate_today = bool(selected_symbol) and _count_today_submitted_orders(project_root, symbol=selected_symbol) > 0

    live_auto_ready = all(bool(v) for v in checks.values())
    live_start_blockers = [k for k, v in checks.items() if not v]

    reason = "LIVE_ORDER_SUBMIT_ENABLED"
    next_blocking_point = None

    def _block(code: str) -> None:
        nonlocal reason, next_blocking_point
        if reason == "LIVE_ORDER_SUBMIT_ENABLED":
            reason = code
            next_blocking_point = code

    if not checks.get("LIVE_TRADING_ENABLED_TRUE", False):
        _block("LIVE_TRADING_ENABLED=false")
    elif not checks.get("CONFIRM_ENV_SET", False):
        _block("SAT3_CONFIRM_LIVE_AUTO_TRADING not confirmed")
    elif not checks.get("SESSION_REGULAR_MARKET", False):
        _block("SESSION_STATE_NOT_REGULAR_MARKET")
    elif not checks.get("MARKET_REGIME_KNOWN", False):
        _block("MARKET_REGIME_UNKNOWN")
    elif not checks.get("KIS_REST_AVAILABLE", False) or not checks.get("KIS_REST_FRESH", False):
        _block("REST_SNAPSHOT_NOT_FRESH")
    elif not checks.get("KIS_WS_FRESH", False):
        _block("WS_SNAPSHOT_NOT_FRESH")
    elif not checks.get("OPEN_ORDER_RECONCILIATION_KNOWN", False):
        _block("OPEN_ORDER_UNKNOWN")
    elif open_order_pending:
        _block("OPEN_ORDER_PENDING")
    elif token_expired:
        _block(token_reason)
    elif not account_parts_ok:
        _block("ACCOUNT_PARTS_INVALID")
    elif not balance_ok:
        _block("BALANCE_UNAVAILABLE")
    elif not orderable_ok:
        _block("ORDERABLE_UNAVAILABLE")
    elif not cash_ok:
        _block("CASH_UNAVAILABLE")
    elif not selected_candidate:
        _block("SELECTED_CANDIDATE_MISSING")
    elif selected_product_type != "COMMON_STOCK":
        _block(f"PRODUCT_TYPE_NOT_COMMON_STOCK:{selected_product_type or 'UNKNOWN'}")
    elif not strategy_buy:
        _block("STRATEGY_NOT_BUY")
    elif not risk_allowed:
        _block("RISK_NOT_ALLOWED")
    elif not allow_new_buy:
        _block("ALLOW_NEW_BUY_FALSE")
    elif not audit_ready:
        _block("AUDIT_DB_UNAVAILABLE")
    elif submitted_today >= daily_limit:
        _block("DAILY_ORDER_LIMIT_EXCEEDED")
    elif duplicate_guard_enabled and duplicate_today:
        _block("DUPLICATE_ORDER_GUARD_BLOCKED")

    enabled = reason == "LIVE_ORDER_SUBMIT_ENABLED"
    return {
        "order_submit_enabled": enabled,
        "order_submit_enabled_reason": reason if not enabled else "",
        "next_blocking_point": next_blocking_point,
        "live_auto_ready": live_auto_ready,
        "live_start_blockers": live_start_blockers,
        "checks": {
            "session_state_regular_market": bool(checks.get("SESSION_REGULAR_MARKET", False)),
            "live_trading_enabled": bool(checks.get("LIVE_TRADING_ENABLED_TRUE", False)),
            "confirm_env_set": bool(checks.get("CONFIRM_ENV_SET", False)),
            "open_order_state_known": open_order_known,
            "open_order_pending": open_order_pending,
            "open_order_state_source": str(open_order_state.get("source", "")),
            "open_order_state_reason": str(open_order_state.get("reason", "")),
            "open_order_state_blocker": str(open_order_state.get("blocker", "")),
            "token_expired": token_expired,
            "balance_ok": balance_ok,
            "orderable_ok": orderable_ok,
            "cash_ok": cash_ok,
            "allow_new_buy": allow_new_buy,
            "audit_ready": audit_ready,
            "daily_order_limit": daily_limit,
            "orders_submitted_today": submitted_today,
            "duplicate_guard_enabled": duplicate_guard_enabled,
            "duplicate_order_today": duplicate_today,
            "risk_allowed": risk_allowed,
            "strategy_buy": strategy_buy,
            "product_type": selected_product_type or "UNKNOWN",
            "selected_symbol": selected_symbol,
            "account_parts_ok": account_parts_ok,
        },
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
            if mode != "dry-run":
                from dashboard.dashboard_routes import run_runtime_tick_and_sync
                tick = run_runtime_tick_and_sync(mode="live", session=session)
            else:
                from dashboard.dashboard_routes import run_runtime_tick_and_sync
                tick = run_runtime_tick_and_sync(mode="dry-run", session=session)
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
    if mode == "dry-run":
        tick = run_runtime_tick_and_sync(mode="dry-run", session=session)
    else:
        checks, _ctx = _build_live_start_checks()
        failed = [k for k, v in checks.items() if not v]
        if failed:
            return {
                "mode": mode,
                "status": "RUNTIME_LIVE_MODE_BLOCKED",
                "reason": "LIVE_START_PRECONDITION_FAILED",
                "executed": False,
                "block_reasons": failed,
            }
        tick = run_runtime_tick_and_sync(mode="live", session=session)

    with _runtime_lock:
        _runtime_status["mode"] = mode
        _runtime_status["session"] = session
        _runtime_status["last_result"] = tick
        _runtime_status["tick_count"] = int(_runtime_status.get("tick_count", 0)) + 1
        _runtime_status["last_tick_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return tick


@app.post("/api/runtime/start")
async def runtime_start(mode: str = "dry-run", session: str = "REGULAR_MARKET", interval_sec: int = 10):
    global _runtime_thread
    with _runtime_lock:
        if _runtime_status.get("running"):
            return {"started": False, "reason": "already_running", "status": _runtime_status}

    if mode == "live":
        checks, ctx = _build_live_start_checks()
        failed = [k for k, v in checks.items() if not v]
        with _runtime_lock:
            _runtime_status["running"] = False
            _runtime_status["mode"] = "live"
            _runtime_status["session"] = session
            _runtime_status["live_start_block_reasons"] = failed
            _runtime_status["last_result"] = {"checks": checks, "context": ctx}
        if failed:
            return {"started": False, "reason": "LIVE_START_PRECONDITION_FAILED", "block_reasons": failed, "status": _runtime_status}

    with _runtime_lock:
        _runtime_stop_event.clear()
        _runtime_status["running"] = True
        _runtime_status["mode"] = mode
        _runtime_status["session"] = session
        _runtime_status["interval_sec"] = max(5, int(interval_sec))

    _runtime_thread = threading.Thread(target=_runtime_loop, daemon=True)
    _runtime_thread.start()
    with _runtime_lock:
        return {"started": True, "status": _runtime_status}


@app.post("/api/runtime/start-live")
async def runtime_start_live(payload: dict | None = None):
    payload = payload or {}
    confirm = str(payload.get("confirm", ""))
    if confirm != "CONFIRM_LIVE_AUTO_TRADING":
        return {
            "started": False,
            "reason": "LIVE_CONFIRM_REQUIRED",
            "required_confirm": "CONFIRM_LIVE_AUTO_TRADING",
        }
    # 운영 정책: CONFIRM 환경변수는 운영자가 수동으로 설정해야 하며 API가 자동 설정하지 않는다.
    confirm_account = str(payload.get("confirm_account", "") or "").strip()
    configured_account = str(os.getenv("KIS_ACCOUNT_NO", "") or "").strip()
    if not confirm_account:
        return {
            "started": False,
            "reason": "LIVE_CONFIRM_ACCOUNT_REQUIRED",
        }
    if not configured_account:
        return {
            "started": False,
            "reason": "LIVE_CONFIG_ACCOUNT_MISSING",
        }
    if confirm_account != configured_account:
        return {
            "started": False,
            "reason": "LIVE_CONFIRM_ACCOUNT_MISMATCH",
        }
    interval_sec = int(payload.get("interval_sec", 10) or 10)
    return await runtime_start(mode="live", session="REGULAR_MARKET", interval_sec=interval_sec)


@app.post("/api/runtime/stop")
async def runtime_stop():
    _runtime_stop_event.set()
    with _runtime_lock:
        _runtime_status["running"] = False
    return {"stopped": True, "status": _runtime_status}


@app.get("/api/runtime/status")
async def runtime_status():
    with _runtime_lock:
        status = dict(_runtime_status)
    try:
        from dashboard.dashboard_routes import handle_get_summary

        summary = handle_get_summary()
        order_state = summary.get("order_submit_state") if isinstance(summary, dict) else {}
        order_state = order_state if isinstance(order_state, dict) else {}
        status["order_submit_enabled"] = bool(order_state.get("order_submit_enabled", status.get("order_submit_enabled", False)))
        status["order_submit_enabled_reason"] = str(order_state.get("order_submit_enabled_reason", status.get("order_submit_enabled_reason", "")))
        status["order_submit_checks"] = dict(order_state.get("checks") or {})
        status["live_auto_ready"] = bool(summary.get("live_auto_ready", False))
        status["live_start_blockers"] = list(summary.get("live_start_blockers", []) or [])
    except Exception:
        pass
    return status


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
