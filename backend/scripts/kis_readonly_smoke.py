"""KIS Read-Only Smoke Test — 조회 전용 수동 검증

이 스크립트는 실제 KIS API 자격증명으로 조회 API가 정상 동작하는지 확인합니다.
주문 endpoint는 절대 호출하지 않습니다.
LIVE_TRADING_ENABLED=false가 아니면 실행을 거부합니다.

사용법:
    PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py
    PYTHONPATH=./backend .venv/bin/python backend/scripts/kis_readonly_smoke.py --symbol 000660

⚠️ 실제 KIS 서버를 호출합니다. 테스트 용도로만 사용하세요.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

DEFAULT_SYMBOL = "005930"


def run_smoke_with_transport(
    transport,
    symbol: str,
    app_key: str,
    app_secret: str,
    base_url: str,
    account_no: str = "",
) -> dict[str, Any]:
    """StubTransport 또는 RealTransport로 smoke 테스트 실행"""
    from kis.credentials import KisCredentials
    from kis.token_provider import KisTokenProvider
    from kis.query_facade import KisQueryFacade
    from kis.client import KisClient

    creds = KisCredentials(
        app_key=app_key, app_secret=app_secret,
        base_url=base_url, account_no=account_no or None,
    )

    results: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "credentials": creds.masked_dict(),
    }

    try:
        # 1. LIVE_TRADING_ENABLED 확인
        live_enabled = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
        results["live_trading_enabled"] = live_enabled
        if live_enabled == "true":
            results["error"] = "LIVE_TRADING_ENABLED=true — ABORTED"
            return results

        # 2. Token 발급
        provider = KisTokenProvider(
            app_key=app_key, app_secret=app_secret,
            base_url=base_url, transport=transport,
        )
        token = provider.issue_token()
        results["token"] = "OK"
    except Exception as e:
        results["token"] = f"FAIL: {_safe_error(e)}"
        return results

    # 3. Client with auth
    from kis.client import KisClient
    client = KisClient(
        base_url=base_url, transport=transport,
        app_key=app_key, app_secret=app_secret,
    )
    client.auth_manager.set_token(token)

    facade = KisQueryFacade(client=client)

    # 4. 휴장일조회
    try:
        holidays = facade.get_holidays()
        results["holidays"] = f"OK ({len(holidays)} days)" if holidays else "OK (empty)"
    except Exception as e:
        results["holidays"] = f"FAIL: {_safe_error(e)}"

    # 5. 장운영정보
    try:
        status = facade.get_market_status()
        results["market_status"] = status.get("market_status", "unknown")
    except Exception as e:
        results["market_status"] = f"FAIL: {_safe_error(e)}"

    # 6. 현재가 조회
    try:
        price = facade.get_current_price(symbol)
        if price.get("data_available"):
            p = price.get("current_price", "?")
            results["price"] = f"OK ({p} won)"
            results["last_price"] = p
            results["change_rate"] = price.get("change_rate")
            results["observed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            results["price"] = "DataUnavailable"
    except Exception as e:
        results["price"] = f"FAIL: {_safe_error(e)}"

    # 7. 계좌/잔고 조회 (readonly)
    try:
        from kis.account_api import AccountApi
        account_api = AccountApi(client=client)
        balance = account_api.get_balance()
        positions = balance.get("positions", []) if isinstance(balance, dict) else []
        results["balance"] = f"OK (positions={len(positions)})"
    except Exception as e:
        results["balance"] = f"FAIL: {_safe_error(e)}"

    # 8. 종목정보 (선택)
    try:
        info = facade.get_stock_info(symbol)
        results["stock_info"] = f"{info.get('market', '?')}/{info.get('product_type', '?')}"
    except Exception as e:
        results["stock_info"] = f"FAIL: {_safe_error(e)}"

    return results


def _safe_error(e: Exception) -> str:
    """secret 원문이 포함되지 않은 에러 메시지"""
    msg = str(e)
    for word in ["appkey", "appsecret", "secret", "token:", "access_token",
                 "PSH", "44413716"]:
        if word.lower() in msg.lower():
            return type(e).__name__
    return f"{type(e).__name__}: {msg[:80]}"


def _save_snapshot(result: dict[str, Any]) -> None:
    """Save sanitized readonly smoke snapshot for dashboard consumption."""
    try:
        import json
        from pathlib import Path

        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        price_text = str(result.get("price", ""))
        sample_price = 0
        if price_text.startswith("OK (") and " won" in price_text:
            raw = price_text.split("OK (", 1)[1].split(" won", 1)[0]
            sample_price = int(raw.replace(",", "").strip() or 0)

        snapshot = {
            "timestamp": result.get("timestamp", ""),
            "symbol": result.get("symbol", "005930"),
            "token": result.get("token", ""),
            "price": result.get("price", ""),
            "last_price": result.get("last_price", sample_price),
            "change_rate": result.get("change_rate"),
            "observed_at": result.get("observed_at", result.get("timestamp", "")),
            "balance": result.get("balance", ""),
            "success": str(result.get("token", "")).startswith("OK") and str(result.get("price", "")).startswith("OK"),
            "sample_price": sample_price,
            "mode": "readonly_rest_smoke",
        }
        (data_dir / "kis_readonly_smoke_snapshot.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        # snapshot persistence failure must not fail smoke execution
        pass


def _debug_response_keys(transport, base_url: str, symbol: str) -> None:
    """응답 key 구조만 출력 (값 출력 금지)"""
    from kis.client import KisClient
    client = KisClient(base_url=base_url, transport=transport,
                       app_key="***", app_secret="***")

    # Use endpoint catalog names (no placeholder paths).
    # Values must never be printed; we only show key structure.
    endpoints = [
        ("market-status", "inquire_market_status", None),
        ("price", "inquire_price", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}),
        ("stock-basic", "inquire_stock_basic", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}),
        # balance is optional and requires account params (handled by AccountApi in normal flow)
    ]

    for name, endpoint_name, params in endpoints:
        try:
            resp = client.get_json(endpoint_name, params=params)
            body = resp.body
            # key 목록만 안전하게 출력
            top_keys = list(body.keys())
            safe_keys = [k for k in top_keys if k.lower() not in
                         ("appkey", "appsecret", "token", "access_token",
                          "authorization", "account_no", "chat_id")]
            print(f"  [{name}] top_keys: {safe_keys}")
            for out_k in ("output", "output1", "output2"):
                if out_k in body and isinstance(body[out_k], dict):
                    inner_keys = list(body[out_k].keys())
                    safe_inner = [k for k in inner_keys if k.lower() not in
                                  ("appkey", "appsecret", "token", "access_token",
                                   "account_no", "chat_id")]
                    print(f"    {out_k} keys: {safe_inner}")
        except Exception as e:
            print(f"  [{name}] error: {_safe_error(e)}")


def main():
    use_real = "--real" in sys.argv
    use_debug_keys = "--debug-keys" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    symbol = args[0] if args else DEFAULT_SYMBOL

    from dotenv import load_dotenv
    load_dotenv()

    app_key = os.getenv("KIS_APP_KEY", "")
    app_secret = os.getenv("KIS_APP_SECRET", "")
    base_url = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
    account_no = os.getenv("KIS_ACCOUNT_NO", "")

    if not app_key or not app_secret:
        print("ERROR: KIS_APP_KEY and KIS_APP_SECRET must be set in .env")
        sys.exit(1)

    # Transport 선택
    transport = None
    if use_real:
        from kis.transport import RealTransport
        transport = RealTransport(base_url=base_url, timeout=30)
        transport_mode = "REAL"
    else:
        from kis.transport import StubTransport
        transport = StubTransport()
        transport_mode = "STUB"

    print("=" * 50)
    print("SAT3 KIS Read-Only Smoke Test")
    print("=" * 50)
    print(f"Symbol: {symbol}")
    print(f"Mode: {transport_mode}")
    print("=" * 50)

    result = run_smoke_with_transport(
        transport=transport,
        symbol=symbol,
        app_key=app_key, app_secret=app_secret,
        base_url=base_url, account_no=account_no,
    )

    for k, v in result.items():
        print(f"  {k}: {v}")

    _save_snapshot(result)

    if result.get("error"):
        sys.exit(1)

    if use_debug_keys:
        print()
        print("=" * 50)
        print("DEBUG KEYS (values masked)")
        print("=" * 50)
        _debug_response_keys(transport, base_url, symbol)


if __name__ == "__main__":
    main()
