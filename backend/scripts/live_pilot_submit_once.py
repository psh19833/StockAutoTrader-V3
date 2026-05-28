#!/usr/bin/env python3
"""SAT3 Live Pilot Submit-Once Guard

목적:
- forced_live_autotrade_preview.py가 생성한 preview JSON을 입력으로 받아,
  조건을 만족할 때만 'submit_cash_order'를 1회 호출할 수 있는 submit-once 경로 제공.

안전 원칙:
- 기본은 BLOCK(실주문 방지).
- 이번 구현/테스트에서는 실제 KIS 주문 API 호출을 하지 않는다.
  (테스트는 mock submitter만 사용)
- 실전 사용 시에도 주문 endpoint 허용은 이 스크립트 내부의 전용 transport 경로로만 제한한다.

출력/저장:
- logs/ 아래에 lock/request/response/final 파일 생성 (민감정보는 redaction)

NOTE:
- 이 스크립트는 live runner/runtime tick과 분리된 1회성 pilot 용도다.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit_logging.audit_event import AuditEvent
from audit_logging.audit_repo_bridge import save_audit_event
from kis.order_api import build_cash_order_payload
from storage.database import init_db
from storage.sqlite_repositories import SqliteAuditEventRepository


CONFIRM_STRING = "CONFIRM_LIVE_PILOT_SUBMIT_ONCE"
FINAL_CONFIRM_STRING = "EXECUTE_REAL_KIS_ORDER_ONCE"


def _build_real_guarded_submitter():
    """Build real GuardedKisCashOrderSubmitter (wiring only).

    Policy:
    - Do NOT globally unblock order endpoints.
    - Allow ONLY order-cash endpoint via an explicitly constructed order-scoped transport.
    - Do not print secrets.
    """
    from kis.order_api import GuardedKisCashOrderSubmitter
    from kis.token_provider import KisTokenProvider
    from kis.order_scoped_transport import OrderScopedRealTransport

    base_url = str(os.getenv("KIS_BASE_URL", "") or "").strip()
    app_key = str(os.getenv("KIS_APP_KEY", "") or "").strip()
    app_secret = str(os.getenv("KIS_APP_SECRET", "") or "").strip()
    if not base_url:
        raise RuntimeError("KIS_BASE_URL missing")
    if not app_key or not app_secret:
        raise RuntimeError("KIS_APP_KEY/KIS_APP_SECRET missing")

    transport = OrderScopedRealTransport(
        base_url=base_url,
        timeout=10,
        allow_order_paths=("/uapi/domestic-stock/v1/trading/order-cash",),
    )
    token_provider = KisTokenProvider(
        app_key=app_key,
        app_secret=app_secret,
        base_url=base_url,
        transport=transport,
    )
    return GuardedKisCashOrderSubmitter(
        transport=transport,
        token_provider=token_provider,
        app_key=app_key,
        app_secret=app_secret,
    )


# ── Errors / Codes ───────────────────────────────────────────────────────────

class PilotGuardError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


# ── Redaction ────────────────────────────────────────────────────────────────

_REDACT_KEYS = {
    "authorization",
    "appkey",
    "appsecret",
    "access_token",
    "token",
    "secret",
    "CANO",
    "ACNT_PRDT_CD",
    "CTAC_TLNO",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ACCOUNT_NO",
    "TELEGRAM_BOT_TOKEN",
}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k) in _REDACT_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


# ── Kill switch ──────────────────────────────────────────────────────────────

def _is_emergency_stop_active(project_root: Path) -> bool:
    p = project_root / ".emergency_stop"
    if not p.is_file():
        return False
    try:
        t = p.read_text(encoding="utf-8", errors="replace").lower()
        return "active" in t
    except Exception:
        # Fail-closed: if the file exists but unreadable, treat as active.
        return True


# ── Session check (read-only, injectable) ────────────────────────────────────

def _default_check_session_regular_market() -> tuple[bool, str]:
    """Return (ok, reason) using the verified dashboard session path.

    Reuses the same read-only session classifier that powers
    dashboard/session and returns REGULAR_MARKET only when that path does.
    Fail-closed for UNKNOWN / holiday / after-hours / any lookup error.
    """
    try:
        from dashboard.dashboard_routes import handle_get_session

        session = handle_get_session() or {}
        state = str(session.get("session_state", "") or "").upper()
        reason = str(session.get("reason", "") or "").strip()
        detail = str(session.get("detail", "") or "").strip()

        if state == "REGULAR_MARKET":
            return True, reason or detail or "REGULAR_MARKET"

        if not state:
            return False, "session_source_unavailable"

        return False, reason or detail or state
    except Exception as e:
        return False, f"session_check_error:{type(e).__name__}"


# ── Core guard ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SubmitArtifacts:
    lock_path: Path
    request_path: Path
    response_path: Path
    final_path: Path


def _artifacts(project_root: Path, symbol: str, correlation_id: str) -> SubmitArtifacts:
    today = datetime.now().strftime("%Y%m%d")
    safe_symbol = str(symbol)
    safe_corr = str(correlation_id)
    base = project_root / "logs" / f"live_pilot_submit_once_{today}_{safe_symbol}_{safe_corr}"
    return SubmitArtifacts(
        lock_path=Path(str(base) + ".lock"),
        request_path=Path(str(base) + "_request.json"),
        response_path=Path(str(base) + "_response.json"),
        final_path=Path(str(base) + "_final.txt"),
    )


def _audit_db_path(project_root: Path) -> Path:
    return project_root / "data" / "sat3_audit.db"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _persist_operational_state(
    *,
    project_root: Path,
    preview: dict[str, Any],
    result: dict[str, Any],
    ts: str,
    request_artifact: str,
    response_artifact: str,
    final_artifact: str,
) -> dict[str, Any]:
    db_path = _audit_db_path(project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    try:
        audit_repo = SqliteAuditEventRepository(conn)
        risk = _safe_dict(preview.get("risk"))
        strategy = _safe_dict(preview.get("strategy"))
        scanner = _safe_dict(preview.get("scanner"))
        order_number = str(result.get("kis_order_number", "") or "")
        correlation_id = str(result.get("correlation_id", "") or "")
        symbol = str(result.get("symbol", "") or "")
        side = str(result.get("side", "") or "")
        quantity = int(result.get("quantity", 0) or 0)
        order_status = str(result.get("status", "") or "")
        filled_qty = 0 if order_status == "SUBMITTED" else 0
        filled_price = 0
        remaining_qty = 1 if order_status == "SUBMITTED" else 0

        payload = {
            "order_number": order_number,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": str(result.get("order_type", "") or ""),
            "status": order_status,
            "filled_qty": filled_qty,
            "filled_price": filled_price,
            "remaining_qty": remaining_qty,
            "submitted_at": ts,
            "source": "LIVE_PILOT_ONCE",
            "risk_decision_summary": risk,
            "strategy_summary": strategy,
            "scanner_summary": scanner,
            "artifacts": {
                "request": request_artifact,
                "response": response_artifact,
                "final": final_artifact,
            },
        }
        event_type = "ORDER_SUBMITTED" if order_status == "SUBMITTED" else "ORDER_REJECTED" if order_status == "REJECTED" else "ORDER_FAILED"
        severity = "INFO" if order_status == "SUBMITTED" else "WARNING"
        strategy_name = str(strategy.get("strategy_name") or strategy.get("name") or scanner.get("scanner_type") or "LIVE_PILOT_ONCE")
        event = AuditEvent(
            event_id=f"LP1-{order_number or correlation_id}",
            event_type=event_type,
            severity=severity,
            correlation_id=correlation_id,
            symbol=symbol,
            strategy_name=strategy_name,
            payload=payload,
            source="LIVE_PILOT_ONCE",
        )
        save_audit_event(audit_repo, event)

        risk_decision_id = correlation_id or f"LP1-{order_number}"
        signal_id = str(strategy.get("signal_id") or scanner.get("signal_id") or correlation_id or "")
        conn.execute(
            "INSERT OR REPLACE INTO risk_decisions "
            "(risk_decision_id, signal_id, correlation_id, symbol, side, allowed, reason_code, reason_text, market_regime, session_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                risk_decision_id,
                signal_id,
                correlation_id,
                symbol,
                side,
                1 if bool(risk.get("allowed", order_status == "SUBMITTED")) else 0,
                str(risk.get("reason_code") or risk.get("reason") or result.get("error_code") or ""),
                str(risk.get("reason_text") or risk.get("summary") or result.get("final_result") or ""),
                str(preview.get("market_regime") or risk.get("market_regime") or ""),
                str(preview.get("session_state") or risk.get("session_state") or ""),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO orders "
            "(order_intent_id, risk_decision_id, symbol, side, status, quantity, estimated_amount) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                risk_decision_id,
                risk_decision_id,
                symbol,
                side,
                order_status,
                quantity,
                int(preview.get("order_intent", {}).get("estimated_amount", 0) or 0) if isinstance(preview.get("order_intent"), dict) else 0,
            ),
        )
        if order_status == "SUBMITTED":
            conn.execute(
                "INSERT OR REPLACE INTO fills "
                "(fill_id, order_intent_id, symbol, side, filled_qty, filled_price, remaining_qty) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    order_number or f"LP1-{correlation_id}",
                    risk_decision_id,
                    symbol,
                    side,
                    filled_qty,
                    filled_price,
                    remaining_qty,
                ),
            )

        if scanner or preview.get("scan_run_id"):
            scan_run_id = str(scanner.get("scan_run_id") or preview.get("scan_run_id") or f"LP1-{correlation_id}")
            scanner_type = str(scanner.get("scanner_type") or scanner.get("name") or "LIVE_PILOT_ONCE")
            collected_count = int(scanner.get("candidate_count", 1 if order_status == "SUBMITTED" else 0) or 0)
            included_count = int(scanner.get("included_count", 1 if order_status == "SUBMITTED" else 0) or 0)
            excluded_count = int(scanner.get("excluded_count", max(0, collected_count - included_count)) or 0)
            conn.execute(
                "INSERT OR REPLACE INTO scan_runs "
                "(scan_run_id, scanner_type, market_regime, collected_count, included_count, excluded_count, started_at, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scan_run_id,
                    scanner_type,
                    str(preview.get("market_regime") or ""),
                    collected_count,
                    included_count,
                    excluded_count,
                    ts,
                    ts,
                ),
            )

        conn.commit()
        return {"saved": True, "db_path": str(db_path)}
    finally:
        conn.close()


def _load_preview_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PilotGuardError("PREVIEW_JSON_MISSING", f"preview json not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        raise PilotGuardError("PREVIEW_JSON_PARSE_ERROR", f"json parse error: {type(e).__name__}")
    if not isinstance(raw, dict):
        raise PilotGuardError("PREVIEW_JSON_INVALID", "preview json must be an object")
    return raw


def _require(cond: bool, code: str, msg: str) -> None:
    if not cond:
        raise PilotGuardError(code, msg)


def _resolve_account_parts_from_env() -> tuple[str, str]:
    from kis.account_api import AccountApi

    api = AccountApi(
        account_no=os.getenv("KIS_ACCOUNT_NO", "") or None,
        account_product_code=os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "") or None,
    )
    cano, prdt = api._get_account_parts()
    return cano, prdt


def guard_and_submit_once(
    *,
    project_root: Path,
    preview_json_path: Path,
    confirm: str,
    correlation_id: str,
    submitter,  # duck-typed
    allow_real_submit: bool = False,
    submitter_factory=None,
    session_checker=_default_check_session_regular_market,
) -> dict[str, Any]:
    """Core function used by CLI and tests.

    Returns a dict summary (safe for logging; already redacted fields where necessary).
    """
    _require(confirm == CONFIRM_STRING, "CONFIRM_MISMATCH", "confirm string mismatch")
    _require(bool(correlation_id.strip()), "CORRELATION_ID_REQUIRED", "correlation_id required")

    preview = _load_preview_json(preview_json_path)

    # 3. actual_order_submitted must be false
    _require(bool(preview.get("actual_order_submitted", False)) is False,
             "PREVIEW_ALREADY_SUBMITTED", "preview indicates actual_order_submitted=true")

    # 4. risk.allowed=true
    risk = preview.get("risk") or {}
    _require(isinstance(risk, dict), "RISK_MISSING", "risk missing")
    _require(bool(risk.get("allowed", False)) is True, "RISK_NOT_ALLOWED", "risk.allowed is not true")

    # 5. order_intent
    intent = preview.get("order_intent") or {}
    _require(isinstance(intent, dict), "ORDER_INTENT_MISSING", "order_intent missing")

    symbol = str(intent.get("symbol", "") or "")
    side = str(intent.get("side", "") or "").upper()
    qty = intent.get("quantity")
    order_type = str(intent.get("order_type", "") or "").upper()

    _require(bool(symbol), "SYMBOL_MISSING", "order_intent.symbol missing")
    _require(side == "BUY", "SIDE_NOT_BUY", "order_intent.side must be BUY")
    try:
        qty_i = int(qty) if qty is not None else 0
    except Exception:
        qty_i = 0
    _require(qty_i == 1, "QTY_NOT_ONE", "order_intent.quantity must be 1")
    _require(order_type == "MARKET", "ORDER_TYPE_NOT_MARKET", "order_intent.order_type must be MARKET")

    # 9. kis_payload_preview
    payload = preview.get("kis_payload_preview") or {}
    _require(isinstance(payload, dict) and bool(payload), "PAYLOAD_MISSING", "kis_payload_preview missing")

    pdno = str(payload.get("PDNO", "") or "")
    ord_dvsn = str(payload.get("ORD_DVSN", "") or "")
    ord_qty = str(payload.get("ORD_QTY", "") or "")
    ord_unpr = str(payload.get("ORD_UNPR", "") or "")

    _require(pdno == symbol, "PDNO_SYMBOL_MISMATCH", "PDNO must match order_intent.symbol")
    _require(ord_dvsn == "01", "ORD_DVSN_INVALID", "ORD_DVSN must be 01 (MARKET)")
    _require(ord_qty == "1", "ORD_QTY_INVALID", "ORD_QTY must be 1")
    _require(ord_unpr == "0", "ORD_UNPR_INVALID", "ORD_UNPR must be 0 for MARKET")

    # 14. kill switch
    _require(not _is_emergency_stop_active(project_root), "EMERGENCY_STOP_ACTIVE", "emergency stop active")

    # 15. session REGULAR_MARKET
    ok_sess, sess_reason = session_checker()
    _require(bool(ok_sess), "SESSION_NOT_REGULAR", f"session not regular: {sess_reason}")

    art = _artifacts(project_root, symbol, correlation_id)
    art.lock_path.parent.mkdir(parents=True, exist_ok=True)

    # 16. lock/receipt file must not exist
    _require(not art.lock_path.exists(), "LOCK_EXISTS", f"lock exists: {art.lock_path.name}")

    # 17. submitter configured
    # - default: caller must pass submitter (tests/mocks)
    # - allow_real_submit=True: build a real submitter ONLY via explicit factory, in this path.
    if submitter is None and allow_real_submit:
        _require(submitter_factory is not None, "SUBMITTER_FACTORY_MISSING", "submitter_factory required")
        submitter = submitter_factory()
    _require(submitter is not None, "SUBMITTER_NOT_CONFIGURED", "submitter is required")

    # Write lock BEFORE submit
    art.lock_path.write_text("locked\n", encoding="utf-8")

    submit_payload = dict(payload)
    if allow_real_submit:
        cano, prdt = _resolve_account_parts_from_env()
        preview_cano = str(payload.get("CANO", "") or "")
        preview_prdt = str(payload.get("ACNT_PRDT_CD", "") or "")
        if preview_cano and preview_cano != cano:
            raise PilotGuardError("CANO_MISMATCH", "preview CANO does not match configured account")
        if preview_prdt and preview_prdt != prdt:
            raise PilotGuardError("ACNT_PRDT_CD_MISMATCH", "preview ACNT_PRDT_CD does not match configured account")
        submit_payload = build_cash_order_payload(
            symbol=symbol,
            side=side,
            qty=qty_i,
            price=int(intent.get("price", 0) or 0),
            order_type=order_type,
            account_no=cano,
            account_product_code=prdt,
        )

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request_redacted = _redact({
        "timestamp": ts,
        "correlation_id": correlation_id,
        "symbol": symbol,
        "side": side,
        "quantity": 1,
        "order_type": order_type,
        "kis_payload_preview": submit_payload,
    })
    art.request_path.write_text(json.dumps(request_redacted, ensure_ascii=False, indent=2), encoding="utf-8")

    result: dict[str, Any] = {
        "timestamp": ts,
        "correlation_id": correlation_id,
        "symbol": symbol,
        "side": side,
        "quantity": 1,
        "order_type": order_type,
        "actual_order_submitted": False,
        "status": "NOT_SUBMITTED",
        "error_code": "",
        "error_message": "",
        "kis_order_number": "",
        "final_result": "",
        "artifacts": {
            "lock": str(art.lock_path),
            "request": str(art.request_path),
            "response": str(art.response_path),
            "final": str(art.final_path),
        },
    }

    try:
        # submitter must provide submit_cash_order(payload, tr_id) OR a submit(...) adapter.
        # For pilot we always BUY cash order.
        from kis.order_api import BUY_TR_ID

        resp_obj = None
        if hasattr(submitter, "submit_cash_order"):
            resp_obj = submitter.submit_cash_order(payload=submit_payload, tr_id=BUY_TR_ID)
        elif hasattr(submitter, "submit"):
            resp_obj = submitter.submit(submit_payload)
        else:
            raise PilotGuardError("SUBMITTER_INVALID", "submitter missing submit_cash_order/submit")

        # Normalize response
        success = bool(getattr(resp_obj, "success", False)) if resp_obj is not None else False
        order_no = str(getattr(resp_obj, "order_number", "") or "") if resp_obj is not None else ""
        msg = str(getattr(resp_obj, "message", "") or "") if resp_obj is not None else ""
        err_t = str(getattr(resp_obj, "error_type", "") or "") if resp_obj is not None else ""

        response_redacted = _redact({
            "success": success,
            "order_number": order_no,
            "message": msg,
            "error_type": err_t,
        })
        art.response_path.write_text(json.dumps(response_redacted, ensure_ascii=False, indent=2), encoding="utf-8")

        result["actual_order_submitted"] = bool(success)
        result["status"] = "SUBMITTED" if success else "REJECTED"
        result["kis_order_number"] = order_no
        result["final_result"] = msg or ("OK" if success else "REJECTED")

        art.final_path.write_text(
            f"timestamp={ts}\nstatus={result['status']}\norder_number={order_no}\nmessage={result['final_result']}\n",
            encoding="utf-8",
        )
        try:
            persist_state = _persist_operational_state(
                project_root=project_root,
                preview=preview,
                result=result,
                ts=ts,
                request_artifact=str(art.request_path),
                response_artifact=str(art.response_path),
                final_artifact=str(art.final_path),
            )
            result["audit_db_saved"] = bool(persist_state.get("saved", False))
            result["audit_db_path"] = str(persist_state.get("db_path", ""))
        except Exception as persist_error:
            result["audit_db_saved"] = False
            result["audit_db_error"] = f"{type(persist_error).__name__}"
        return result

    except PilotGuardError as e:
        # Guard errors inside submit block
        result["status"] = "ERROR"
        result["error_code"] = e.code
        result["error_message"] = e.message
        result["final_result"] = "ERROR"
        art.response_path.write_text(json.dumps(_redact({"error": str(e)}), ensure_ascii=False, indent=2), encoding="utf-8")
        art.final_path.write_text(f"timestamp={ts}\nstatus=ERROR\nerror_code={e.code}\nerror_message={e.message}\n", encoding="utf-8")
        try:
            persist_state = _persist_operational_state(
                project_root=project_root,
                preview=preview,
                result=result,
                ts=ts,
                request_artifact=str(art.request_path),
                response_artifact=str(art.response_path),
                final_artifact=str(art.final_path),
            )
            result["audit_db_saved"] = bool(persist_state.get("saved", False))
            result["audit_db_path"] = str(persist_state.get("db_path", ""))
        except Exception as persist_error:
            result["audit_db_saved"] = False
            result["audit_db_error"] = f"{type(persist_error).__name__}"
        return result

    except Exception as e:
        # Any unexpected exception: record safely.
        result["status"] = "ERROR"
        result["error_code"] = "UNEXPECTED_EXCEPTION"
        result["error_message"] = f"{type(e).__name__}"
        result["final_result"] = "ERROR"
        art.response_path.write_text(json.dumps(_redact({"error": f"{type(e).__name__}"}), ensure_ascii=False, indent=2), encoding="utf-8")
        art.final_path.write_text(f"timestamp={ts}\nstatus=ERROR\nerror_code=UNEXPECTED_EXCEPTION\nerror_message={type(e).__name__}\n", encoding="utf-8")
        try:
            persist_state = _persist_operational_state(
                project_root=project_root,
                preview=preview,
                result=result,
                ts=ts,
                request_artifact=str(art.request_path),
                response_artifact=str(art.response_path),
                final_artifact=str(art.final_path),
            )
            result["audit_db_saved"] = bool(persist_state.get("saved", False))
            result["audit_db_path"] = str(persist_state.get("db_path", ""))
        except Exception as persist_error:
            result["audit_db_saved"] = False
            result["audit_db_error"] = f"{type(persist_error).__name__}"
        return result


def main() -> int:
    p = argparse.ArgumentParser(description="SAT3 submit-once live pilot guard (NO real order in tests)")
    p.add_argument("--preview-json", required=True)
    p.add_argument("--confirm", required=True)
    p.add_argument("--correlation-id", required=True)
    p.add_argument("--dry-run", action="store_true", help="Do not submit; only validate and write final as BLOCKED")
    p.add_argument("--execute-real-submit", action="store_true", help="Execute ONE real submit (requires dual confirm)")
    p.add_argument("--final-confirm", default="", help="Must equal EXECUTE_REAL_KIS_ORDER_ONCE")
    p.add_argument(
        "--allow-real-submit",
        action="store_true",
        help="WIRING ONLY: attempt to build real guarded submitter (still no real submit in this phase)",
    )
    args = p.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    preview_path = Path(args.preview_json)

    # Fail-closed gating.
    if args.execute_real_submit and args.dry_run:
        raise SystemExit("BLOCKED: cannot combine --execute-real-submit with --dry-run")

    if args.execute_real_submit:
        _require(args.confirm == CONFIRM_STRING, "CONFIRM_MISMATCH", "confirm string mismatch")
        _require(args.final_confirm == FINAL_CONFIRM_STRING, "FINAL_CONFIRM_MISMATCH", "final confirm mismatch")
        _require(bool(args.allow_real_submit), "REAL_SUBMIT_REQUIRES_ALLOW_FLAG", "--allow-real-submit is required")
    else:
        # default dry-run
        if not args.dry_run:
            raise SystemExit("BLOCKED: CLI requires --dry-run unless --execute-real-submit is set")

    # Wiring validation / submitter selection
    submitter = None
    if args.execute_real_submit:
        try:
            submitter = _build_real_guarded_submitter()
        except Exception as e:
            raise SystemExit(f"BLOCKED: real submitter wiring failed: {type(e).__name__}")
    elif args.allow_real_submit:
        # Wiring check only (still dry-run)
        _require(args.confirm == CONFIRM_STRING, "CONFIRM_MISMATCH", "confirm string mismatch")
        try:
            _ = _build_real_guarded_submitter()
        except Exception as e:
            raise SystemExit(f"BLOCKED: real submitter wiring failed: {type(e).__name__}")

    # Dry-run validates guards and writes a final marker; real submit path will submit once.
    try:
        # validate only: will fail at SUBMITTER_NOT_CONFIGURED after lock unless we short-circuit.
        # For dry-run, we run all validations but skip submit and avoid creating lock.
        _require(args.confirm == CONFIRM_STRING, "CONFIRM_MISMATCH", "confirm string mismatch")
        _require(bool(args.correlation_id.strip()), "CORRELATION_ID_REQUIRED", "correlation_id required")
        preview = _load_preview_json(preview_path)
        _require(bool(preview.get("actual_order_submitted", False)) is False, "PREVIEW_ALREADY_SUBMITTED", "actual_order_submitted=true")
        risk = preview.get("risk") or {}
        _require(isinstance(risk, dict) and bool(risk.get("allowed", False)) is True, "RISK_NOT_ALLOWED", "risk.allowed must be true")
        intent = preview.get("order_intent") or {}
        _require(isinstance(intent, dict), "ORDER_INTENT_MISSING", "order_intent missing")
        _require(str(intent.get("side", "")).upper() == "BUY", "SIDE_NOT_BUY", "BUY only")
        _require(int(intent.get("quantity", 0)) == 1, "QTY_NOT_ONE", "qty must be 1")
        _require(str(intent.get("order_type", "")).upper() == "MARKET", "ORDER_TYPE_NOT_MARKET", "MARKET only")
        payload = preview.get("kis_payload_preview") or {}
        _require(isinstance(payload, dict) and bool(payload), "PAYLOAD_MISSING", "payload missing")
        _require(str(payload.get("ORD_DVSN", "")) == "01", "ORD_DVSN_INVALID", "ORD_DVSN must be 01")
        _require(str(payload.get("ORD_QTY", "")) == "1", "ORD_QTY_INVALID", "ORD_QTY must be 1")
        _require(str(payload.get("ORD_UNPR", "")) == "0", "ORD_UNPR_INVALID", "ORD_UNPR must be 0")
        _require(str(payload.get("PDNO", "")) == str(intent.get("symbol", "")), "PDNO_SYMBOL_MISMATCH", "PDNO mismatch")
        _require(not _is_emergency_stop_active(project_root), "EMERGENCY_STOP_ACTIVE", "emergency stop active")
        ok_sess, sess_reason = _default_check_session_regular_market()
        _require(bool(ok_sess), "SESSION_NOT_REGULAR", f"session not regular: {sess_reason}")

        symbol = str(intent.get("symbol", ""))

        if args.execute_real_submit:
            # Real submit path: create full artifacts (lock/request/response/final)
            _require(submitter is not None, "SUBMITTER_NOT_CONFIGURED", "submitter missing")
            return_result = guard_and_submit_once(
                project_root=project_root,
                preview_json_path=preview_path,
                confirm=args.confirm,
                correlation_id=str(args.correlation_id),
                submitter=submitter,
                allow_real_submit=True,
            )
            # Print final path for operator convenience (no secrets)
            print(return_result.get("artifacts", {}).get("final", ""))
            return 0 if bool(return_result.get("actual_order_submitted")) else 1

        # Dry-run: final marker only (no lock/request/response)
        art = _artifacts(project_root, symbol, str(args.correlation_id))
        art.final_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        art.final_path.write_text(f"timestamp={ts}\nstatus=DRY_RUN_OK\nmessage=validated_only\n", encoding="utf-8")
        print(str(art.final_path))
        return 0

    except PilotGuardError as e:
        print(f"BLOCKED {e.code}: {e.message}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
