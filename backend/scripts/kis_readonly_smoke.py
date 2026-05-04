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

    # 3. Query Facade
    client = KisClient(
        base_url=base_url, transport=transport,
        app_key=app_key, app_secret=app_secret,
    )
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
            results["price"] = f"OK ({price.get('current_price', '?')} won)"
        else:
            results["price"] = "DataUnavailable"
    except Exception as e:
        results["price"] = f"FAIL: {_safe_error(e)}"

    # 7. 종목정보 (선택)
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


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SYMBOL

    from dotenv import load_dotenv
    load_dotenv()

    app_key = os.getenv("KIS_APP_KEY", "")
    app_secret = os.getenv("KIS_APP_SECRET", "")
    base_url = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
    account_no = os.getenv("KIS_ACCOUNT_NO", "")

    if not app_key or not app_secret:
        print("ERROR: KIS_APP_KEY and KIS_APP_SECRET must be set in .env")
        sys.exit(1)

    # ⚠️ RealTransport는 실제 HTTP 호출 — 운영 환경에서만 사용
    # 이 예제에서는 transport 없이 실행 → KisClient가 TransportResponse(404) 반환
    # 실제 실행 시에는 RealTransport 주입 필요
    print("=" * 50)
    print("SAT3 KIS Read-Only Smoke Test")
    print("=" * 50)
    print(f"Symbol: {symbol}")
    print("WARNING: RealTransport not configured — add transport for actual calls")
    print("=" * 50)

    result = run_smoke_with_transport(
        transport=None,  # RealTransport 필요 시 주입
        symbol=symbol,
        app_key=app_key, app_secret=app_secret,
        base_url=base_url, account_no=account_no,
    )

    for k, v in result.items():
        print(f"  {k}: {v}")

    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
