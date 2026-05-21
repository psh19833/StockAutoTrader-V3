#!/usr/bin/env python3
"""SAT3 Real KIS Account Readonly Check (while LIVE_TRADING_ENABLED=true)

목적:
- 실전 환경에서 LIVE_TRADING_ENABLED=true 상태를 유지한 채,
  주문 endpoint는 계속 차단(RealTransport policy 유지)하면서
  KIS 실계좌 read-only 확인을 수행한다.

허용 호출:
- /oauth2/tokenP (토큰 발급)
- /uapi/domestic-stock/v1/trading/inquire-balance (잔고)
- /uapi/domestic-stock/v1/trading/inquire-psbl-order (매수 가능 조회; best-effort)

금지:
- order-cash/order-credit/order-rvsecncl
- submit_cash_order
- 어떤 주문 제출도 수행하지 않음

출력 정책(콘솔):
- PASS/FAIL 요약 + redacted 정보만
- token/appkey/appsecret/account 원문 출력 금지

저장:
- logs/sat3_real_account_readonly_YYYYMMDD_HHMMSS.json
- logs/sat3_real_account_readonly_YYYYMMDD_HHMMSS_summary.txt
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


KST = timezone(timedelta(hours=9))


_REDACT_KEYS = {
    "authorization",
    "appkey",
    "appsecret",
    "access_token",
    "token",
    "secret",
    "CANO",
    "ACNT_PRDT_CD",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ACCOUNT_NO",
    "KIS_ACCOUNT_PRODUCT_CODE",
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


def _mask_account(raw: str) -> str:
    s = "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "-")
    # Keep suffix only (last 2 of CANO, last 2 of PRDT if present)
    if not s:
        return ""
    if "-" in s:
        left, right = s.split("-", 1)
        left_digits = "".join(ch for ch in left if ch.isdigit())
        right_digits = "".join(ch for ch in right if ch.isdigit())
        return f"****{left_digits[-2:]}-**{right_digits[-1:]}" if left_digits else "[REDACTED]"
    digits = "".join(ch for ch in s if ch.isdigit())
    return f"****{digits[-2:]}" if digits else "[REDACTED]"


def _safe_err(e: Exception) -> str:
    # Never include env-derived secrets.
    msg = str(e)[:120]
    lowered = msg.lower()
    for w in ["appkey", "appsecret", "access_token", "authorization", "bearer", "44413716"]:
        if w in lowered:
            return type(e).__name__
    return f"{type(e).__name__}: {msg}"


def _extract_kis_error(body: dict) -> tuple[str, str]:
    # KIS commonly returns rt_cd/msg_cd/msg1
    try:
        msg_cd = str(body.get("msg_cd", "") or body.get("error_code", "") or "")
        msg1 = str(body.get("msg1", "") or body.get("error_description", "") or "")
        return msg_cd, (msg1[:120] if msg1 else "")
    except Exception:
        return "", ""


def _now_kst_stamp() -> str:
    return datetime.now(KST).strftime("%Y%m%d_%H%M%S")


def main() -> int:
    # load .env without printing
    try:
        from dotenv import load_dotenv

        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env")
    except Exception:
        project_root = Path(__file__).resolve().parents[2]

    stamp = _now_kst_stamp()
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    json_path = logs_dir / f"sat3_real_account_readonly_{stamp}.json"
    summary_path = logs_dir / f"sat3_real_account_readonly_{stamp}_summary.txt"

    live_enabled = os.getenv("LIVE_TRADING_ENABLED", "").strip().lower() == "true"

    base_url = str(os.getenv("KIS_BASE_URL", "") or "").strip() or "https://openapi.koreainvestment.com:9443"
    app_key = str(os.getenv("KIS_APP_KEY", "") or "").strip()
    app_secret = str(os.getenv("KIS_APP_SECRET", "") or "").strip()
    account_no = str(os.getenv("KIS_ACCOUNT_NO", "") or "").strip()
    account_product_code = str(os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "") or "").strip()

    result: dict[str, Any] = {
        "timestamp_kst": datetime.now(KST).isoformat(),
        "mode": "REAL_KIS_ACCOUNT_READONLY",
        "live_trading_enabled": live_enabled,
        "token_issued": False,
        "account_query_ok": False,
        "balance_query_ok": False,
        "orderable_query_ok": False,
        "orderable_cash_present": False,
        "balance_present": False,
        "http_status": {},
        "kis_error_code": {},
        "kis_error_message_redacted": {},
        "account_redacted": _mask_account(account_no),
        "product_code_redacted": ("**" if account_product_code else ""),
        "order_endpoint_called": False,
        "submit_cash_order_called": False,
        "next_blocker": "",
    }

    # Hard safety: we never call order endpoints from this script.
    # Also RealTransport blocks order endpoints globally.

    if not app_key or not app_secret:
        result["next_blocker"] = "KIS_APP_KEY/KIS_APP_SECRET missing"
        _write_outputs(json_path, summary_path, result)
        _print_summary(result)
        return 2

    try:
        from kis.transport import RealTransport
        from kis.token_provider import KisTokenProvider
        from kis.client import KisClient
        from kis.account_api import AccountApi
    except Exception as e:
        result["next_blocker"] = f"IMPORT_ERROR:{type(e).__name__}"
        _write_outputs(json_path, summary_path, result)
        _print_summary(result)
        return 2

    transport = RealTransport(base_url=base_url, timeout=20)

    # 1) Token
    try:
        provider = KisTokenProvider(app_key=app_key, app_secret=app_secret, base_url=base_url, transport=transport)
        token = provider.issue_token()
        result["token_issued"] = True
        result["http_status"]["token"] = 200
    except Exception as e:
        result["http_status"]["token"] = 0
        result["kis_error_code"]["token"] = ""
        result["kis_error_message_redacted"]["token"] = _safe_err(e)
        result["next_blocker"] = "TOKEN_ISSUE_FAILED"
        _write_outputs(json_path, summary_path, result)
        _print_summary(result)
        return 1

    # 2) Client
    client = KisClient(base_url=base_url, transport=transport, app_key=app_key, app_secret=app_secret)
    try:
        client.auth_manager.set_token(token)
    except Exception:
        # If token cannot be set, treat as blocker
        result["next_blocker"] = "TOKEN_SET_FAILED"
        _write_outputs(json_path, summary_path, result)
        _print_summary(result)
        return 1

    # 3) Balance (readonly)
    try:
        # Prefer AccountApi which handles account parsing/params.
        api = AccountApi(client=client, account_no=account_no or None, account_product_code=account_product_code or None)
        bal = api.get_balance()
        ok = bool(bal.get("data_available"))
        result["balance_query_ok"] = ok
        result["balance_present"] = ok
        # Derive "orderable cash present" best-effort from raw endpoint response too.
        # NOTE: AccountApi returns total_buyable if present; keep it only as existence flag.
        result["orderable_cash_present"] = bool(bal.get("total_buyable", 0))
        result["http_status"]["balance"] = 200 if ok else 0
        if not ok:
            result["next_blocker"] = result["next_blocker"] or "BALANCE_UNAVAILABLE"
    except Exception as e:
        result["http_status"]["balance"] = 0
        result["kis_error_code"]["balance"] = ""
        result["kis_error_message_redacted"]["balance"] = _safe_err(e)
        result["next_blocker"] = result["next_blocker"] or "BALANCE_QUERY_FAILED"

    # 4) Orderable cash (readonly) — best-effort call to inquire_psbl_order
    # If account info missing, AccountApi returns data_available False; we still try to validate env here.
    try:
        cano, prdt = api._get_account_parts()  # type: ignore[attr-defined]
        # Minimal params for market buy 1 share; symbol omitted here to avoid accidental coupling.
        # We will use 삼성전자(005930) as a neutral probe symbol unless user passes --symbol later.
        symbol = "005930"
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "PDNO": symbol,
            "ORD_UNPR": "0",
            "ORD_DVSN": "01",
        }
        resp = client.get_json("inquire_psbl_order", params=params)
        result["http_status"]["orderable"] = int(resp.status_code)
        if resp.status_code == 200 and isinstance(resp.body, dict) and resp.body:
            result["orderable_query_ok"] = True
            # presence flag only (do not store values)
            out1 = resp.body.get("output")
            out2 = resp.body.get("output1")
            out = out1 if isinstance(out1, dict) else (out2 if isinstance(out2, dict) else {})
            # Common fields in KIS: ord_psbl_cash / ord_psbl_amt / nrcvb_buy_amt...
            present = False
            if isinstance(out, dict):
                for k in ["ord_psbl_cash", "ord_psbl_amt", "nrcvb_buy_amt", "max_buy_amt", "buy_psbl_amt"]:
                    if k in out:
                        present = True
                        break
            result["orderable_cash_present"] = result["orderable_cash_present"] or present
        else:
            result["orderable_query_ok"] = False
            if isinstance(resp.body, dict):
                cd, msg = _extract_kis_error(resp.body)
                result["kis_error_code"]["orderable"] = cd
                result["kis_error_message_redacted"]["orderable"] = msg
            result["next_blocker"] = result["next_blocker"] or "ORDERABLE_QUERY_FAILED"
    except Exception as e:
        result["http_status"]["orderable"] = 0
        result["kis_error_message_redacted"]["orderable"] = _safe_err(e)
        result["next_blocker"] = result["next_blocker"] or "ORDERABLE_QUERY_EXCEPTION"

    # Finalize
    if result["token_issued"] and (result["balance_query_ok"] or result["orderable_query_ok"]):
        if not result["next_blocker"]:
            result["next_blocker"] = ""
    else:
        result["next_blocker"] = result["next_blocker"] or "READONLY_CHECK_INCOMPLETE"

    _write_outputs(json_path, summary_path, result)
    _print_summary(result)

    # exit code
    if result["token_issued"] and result["balance_query_ok"] and result["orderable_query_ok"]:
        return 0
    if result["token_issued"]:
        return 1
    return 2


def _write_outputs(json_path: Path, summary_path: Path, result: dict[str, Any]) -> None:
    safe = _redact(dict(result))
    json_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"timestamp_kst={safe.get('timestamp_kst','')}",
        f"mode={safe.get('mode','')}",
        f"live_trading_enabled={safe.get('live_trading_enabled', False)}",
        f"token_issued={safe.get('token_issued', False)}",
        f"balance_query_ok={safe.get('balance_query_ok', False)}",
        f"orderable_query_ok={safe.get('orderable_query_ok', False)}",
        f"orderable_cash_present={safe.get('orderable_cash_present', False)}",
        f"account_redacted={safe.get('account_redacted','')}",
        f"order_endpoint_called={safe.get('order_endpoint_called', False)}",
        f"submit_cash_order_called={safe.get('submit_cash_order_called', False)}",
        f"next_blocker={safe.get('next_blocker','')}",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_summary(result: dict[str, Any]) -> None:
    # Console output: strictly redacted fields only.
    print("SAT3 REAL ACCOUNT READONLY CHECK")
    print(f"  live_trading_enabled: {bool(result.get('live_trading_enabled'))}")
    print(f"  token_issued: {bool(result.get('token_issued'))}")
    print(f"  balance_query_ok: {bool(result.get('balance_query_ok'))}")
    print(f"  orderable_query_ok: {bool(result.get('orderable_query_ok'))}")
    print(f"  orderable_cash_present: {bool(result.get('orderable_cash_present'))}")
    print(f"  http_status: {result.get('http_status', {})}")
    print(f"  kis_error_code: {result.get('kis_error_code', {})}")
    print(f"  account_redacted: {result.get('account_redacted', '')}")
    nb = str(result.get('next_blocker', '') or '')
    print(f"  next_blocker: {nb}")


if __name__ == "__main__":
    raise SystemExit(main())
