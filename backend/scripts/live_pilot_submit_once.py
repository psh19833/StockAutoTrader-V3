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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIRM_STRING = "CONFIRM_LIVE_PILOT_SUBMIT_ONCE"


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
    """Return (ok, reason). Must not use order endpoints.

    Implementation: uses TradingCalendar+MarketClock with KIS schedule API client if available.
    If API is not connected/available -> BLOCK (fail-closed).

    Tests should override this checker.
    """
    try:
        # Local imports to keep script import-light.
        from session.trading_calendar import TradingCalendar
        from session.market_clock import MarketClock
        from kis.market_schedule_api import MarketScheduleApi
        from kis.transport import RealTransport

        base_url = str(os.getenv("KIS_BASE_URL", "") or "").strip()
        if not base_url:
            return False, "KIS_BASE_URL missing"

        # Read-only: holiday/status endpoints are GET.
        transport = RealTransport(base_url=base_url, timeout=8)
        api = MarketScheduleApi(transport=transport)

        # The MarketScheduleApi returns list[str] like YYYYMMDD.
        def _fetch_holidays() -> tuple[datetime.date, ...]:  # type: ignore[name-defined]
            from datetime import date as dt_date
            items = api.get_holidays() or []
            out = []
            for s in items:
                try:
                    if len(str(s)) == 8:
                        y = int(str(s)[0:4]); m = int(str(s)[4:6]); d = int(str(s)[6:8])
                        out.append(dt_date(y, m, d))
                except Exception:
                    continue
            return tuple(out)

        def _fetch_market_status() -> str:
            ms = api.get_market_status() or {}
            # Normalize to MarketClock.map_kis_status short forms.
            v = str(ms.get("market_status", "unknown") or "unknown").upper()
            if v in {"OPEN", "STATUS_OPEN"}:
                return "OPEN"
            if v in {"CLOSE", "STATUS_CLOSE"}:
                return "CLOSE"
            if v in {"PREOPEN", "STATUS_PREOPEN"}:
                return "PREOPEN"
            return v

        cal = TradingCalendar(fetch_holidays_fn=_fetch_holidays)
        snap = cal.check_today()
        clk = MarketClock(fetch_market_status_fn=_fetch_market_status)
        sess = clk.evaluate(snap)
        ok = str(sess.session_state.value) == "REGULAR_MARKET"
        return ok, sess.reason or str(sess.session_state.value)
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


def guard_and_submit_once(
    *,
    project_root: Path,
    preview_json_path: Path,
    confirm: str,
    correlation_id: str,
    submitter,  # duck-typed
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
    _require(submitter is not None, "SUBMITTER_NOT_CONFIGURED", "submitter is required")

    # Write lock BEFORE submit
    art.lock_path.write_text("locked\n", encoding="utf-8")

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request_redacted = _redact({
        "timestamp": ts,
        "correlation_id": correlation_id,
        "symbol": symbol,
        "side": side,
        "quantity": 1,
        "order_type": order_type,
        "kis_payload_preview": payload,
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
            resp_obj = submitter.submit_cash_order(payload=payload, tr_id=BUY_TR_ID)
        elif hasattr(submitter, "submit"):
            resp_obj = submitter.submit(payload)
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
        return result

    except PilotGuardError as e:
        # Guard errors inside submit block
        result["status"] = "ERROR"
        result["error_code"] = e.code
        result["error_message"] = e.message
        result["final_result"] = "ERROR"
        art.response_path.write_text(json.dumps(_redact({"error": str(e)}), ensure_ascii=False, indent=2), encoding="utf-8")
        art.final_path.write_text(f"timestamp={ts}\nstatus=ERROR\nerror_code={e.code}\nerror_message={e.message}\n", encoding="utf-8")
        return result

    except Exception as e:
        # Any unexpected exception: record safely.
        result["status"] = "ERROR"
        result["error_code"] = "UNEXPECTED_EXCEPTION"
        result["error_message"] = f"{type(e).__name__}"
        result["final_result"] = "ERROR"
        art.response_path.write_text(json.dumps(_redact({"error": f"{type(e).__name__}"}), ensure_ascii=False, indent=2), encoding="utf-8")
        art.final_path.write_text(f"timestamp={ts}\nstatus=ERROR\nerror_code=UNEXPECTED_EXCEPTION\nerror_message={type(e).__name__}\n", encoding="utf-8")
        return result


def main() -> int:
    p = argparse.ArgumentParser(description="SAT3 submit-once live pilot guard (NO real order in tests)")
    p.add_argument("--preview-json", required=True)
    p.add_argument("--confirm", required=True)
    p.add_argument("--correlation-id", required=True)
    p.add_argument("--dry-run", action="store_true", help="Do not submit; only validate and write final as BLOCKED")
    args = p.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    preview_path = Path(args.preview_json)

    # In CLI mode, we default to dry-run unless explicitly opted out.
    # This prevents accidental real submission.
    if not args.dry_run:
        raise SystemExit("BLOCKED: CLI requires --dry-run for now (no real submission enabled in this phase)")

    # Dry-run uses a None submitter; we only validate guards.
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

        # Write a dry-run final file only (no lock/request/response)
        symbol = str(intent.get("symbol", ""))
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
