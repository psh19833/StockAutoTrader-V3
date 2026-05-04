#!/usr/bin/env python3
"""KIS WebSocket Read-Only Smoke Test

SAT3-N8-B: WebSocket smoke 준비 스크립트.
기본값은 StubWebSocketClient를 사용하며, --real-ws 옵션에서만
GuardedRealWebSocketClient를 통해 실제 연결을 시도한다.

사용법:
  # Stub 모드 (기본)
  PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py

  # Stub 모드 + 특정 종목
  PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --symbol 005930

  # 실제 WS 연결 시도 (GuardedRealWebSocketClient)
  PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --real-ws

  # 채널 선택
  PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --channels trade_tick,order_book

  # 체결통보 포함 (기본 제외)
  PYTHONPATH=./backend python backend/scripts/kis_ws_readonly_smoke.py --include-fill-notice

원칙:
  - LIVE_TRADING_ENABLED=true 시 즉시 중단
  - approval_key 원문 출력 금지
  - raw WebSocket 전문 전체 출력 금지
  - parsed summary만 출력
  - 주문 endpoint 호출 금지
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

# ── Path setup ───────────────────────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Load .env
try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(_BACKEND_DIR), ".env")
    load_dotenv(_ENV_PATH)
except ImportError:
    pass


# ── Channel definitions ──────────────────────────────────────────────────────

CHANNEL_TR_ID_MAP = {
    "trade_tick": "H0STCNT0",
    "order_book": "H0STASP0",
    "market_status": "H0STMKO0",
    "expected_execution": "H0STANC0",
    "fill_notice": "H0STCNI0",
}

DEFAULT_CHANNELS = ["trade_tick", "order_book", "market_status", "expected_execution"]

MASKED_APPROVAL_KEY = "****-****-****"


# ── Helper functions ─────────────────────────────────────────────────────────

def _mask_dict(d: dict, keys: set) -> dict:
    """Return a copy of d with specified keys masked."""
    result = dict(d)
    for k in keys:
        if k in result:
            result[k] = MASKED_APPROVAL_KEY
    return result


def _check_live_trading() -> None:
    """Abort if LIVE_TRADING_ENABLED is true."""
    val = os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower()
    if val in ("true", "1", "yes"):
        print("FATAL: LIVE_TRADING_ENABLED=true. Smoke test aborted.")
        sys.exit(1)


def _issue_approval_key(credentials) -> Optional[str]:
    """Issue approval_key and return it. Displays masked only."""
    from kis.ws_approval import WsApprovalKey, ApprovalKeyError
    from kis.transport import RealTransport

    transport = RealTransport(base_url=credentials.base_url)
    approval = WsApprovalKey(credentials=credentials, transport=transport)
    try:
        key = approval.issue()
        print(f"[OK] approval_key issued: {approval.get_masked()}")
        return key
    except ApprovalKeyError as e:
        print(f"[FAIL] approval_key issue failed: {e}")
        return None


def _print_subscribe_payload_masked(tr_id: str, symbol: str, approval_key: str) -> None:
    """Print subscribe payload with approval_key masked."""
    payload = {
        "header": {
            "approval_key": MASKED_APPROVAL_KEY,
            "custtype": "P",
            "tr_type": "1",
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": symbol,
            },
        },
    }
    print(f"  Subscribe payload (masked): {json.dumps(payload, indent=4)}")


def _print_parsed_summary(result) -> None:
    """Print parsed message summary (no raw body)."""
    summary = {
        "tr_id": result.tr_id,
        "symbol": result.symbol,
        "parsed_ok": result.parsed_ok,
        "source": result.source,
        "data_quality_warnings": result.data_quality_warnings,
    }
    # Add type-specific summary
    from kis.ws_models import (
        RealtimeTradeTick, RealtimeOrderBook, RealtimeFillNotice,
        RealtimeMarketStatus, RealtimeExpectedExecution,
    )
    if isinstance(result, RealtimeTradeTick):
        summary["trade_price"] = result.trade_price
        summary["trade_volume"] = result.trade_volume
    elif isinstance(result, RealtimeOrderBook):
        summary["ask_levels"] = len(result.ask_prices)
        summary["bid_levels"] = len(result.bid_prices)
    elif isinstance(result, RealtimeFillNotice):
        summary["fill_price"] = result.fill_price
        summary["fill_volume"] = result.fill_volume
    elif isinstance(result, RealtimeMarketStatus):
        summary["market_status"] = result.market_status
    elif isinstance(result, RealtimeExpectedExecution):
        summary["expected_price"] = result.expected_price

    print(f"  Parsed: {json.dumps(summary, default=str, indent=4)}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="KIS WebSocket Read-Only Smoke Test (N8-B)"
    )
    parser.add_argument(
        "--symbol", default="005930",
        help="Stock symbol (default: 005930)"
    )
    parser.add_argument(
        "--channels", default=",".join(DEFAULT_CHANNELS),
        help=f"Comma-separated channels (default: {','.join(DEFAULT_CHANNELS)})"
    )
    parser.add_argument(
        "--include-fill-notice", action="store_true",
        help="Include fill_notice channel (excluded by default)"
    )
    parser.add_argument(
        "--real-ws", action="store_true",
        help="Use GuardedRealWebSocketClient (attempts real connection)"
    )
    parser.add_argument(
        "--duration", type=int, default=30,
        help="Max duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--max-messages", type=int, default=10,
        help="Max messages to receive (default: 10)"
    )
    args = parser.parse_args()

    # ── Safety: LIVE_TRADING_ENABLED check ────────────────────────────────
    _check_live_trading()

    # ── Parse channels ────────────────────────────────────────────────────
    channel_names = [c.strip() for c in args.channels.split(",") if c.strip()]
    if args.include_fill_notice and "fill_notice" not in channel_names:
        channel_names.append("fill_notice")

    # Validate
    for ch in channel_names:
        if ch not in CHANNEL_TR_ID_MAP:
            print(f"[ERROR] Unknown channel: {ch}")
            print(f"  Available: {', '.join(sorted(CHANNEL_TR_ID_MAP.keys()))}")
            sys.exit(1)

    # ── Create client ─────────────────────────────────────────────────────
    if args.real_ws:
        from kis.ws_client import GuardedRealWebSocketClient
        client = GuardedRealWebSocketClient()
        print(f"[INFO] Using GuardedRealWebSocketClient (--real-ws)")
    else:
        from kis.ws_client import StubWebSocketClient
        client = StubWebSocketClient()
        print(f"[INFO] Using StubWebSocketClient (stub mode)")

    # ── Load credentials ──────────────────────────────────────────────────
    from kis.credentials import KisCredentials
    credentials = KisCredentials.from_env()
    print(f"[INFO] Credentials loaded: {credentials.masked_dict()}")

    # ── Issue approval_key ────────────────────────────────────────────────
    approval_key = None
    if args.real_ws:
        approval_key = _issue_approval_key(credentials)
        if approval_key is None:
            print("[FAIL] Cannot proceed without approval_key.")
            sys.exit(1)
    else:
        # Stub mode: use a fake key
        approval_key = "stub-approval-key-00000000"
        print(f"[INFO] Stub approval_key: {MASKED_APPROVAL_KEY}")

    # ── Connect ───────────────────────────────────────────────────────────
    ws_url = os.getenv("KIS_WEBSOCKET_URL", "")
    if args.real_ws:
        if not ws_url:
            print("[FAIL] KIS_WEBSOCKET_URL not set in .env")
            sys.exit(1)
        try:
            client.connect(approval_key=approval_key, base_url=ws_url)
            print("[OK] WebSocket connected")
        except ConnectionError as e:
            print(f"[FAIL] WebSocket connection failed: {e}")
            sys.exit(1)
    else:
        client.connect()
        print("[OK] WebSocket connected (stub)")

    # ── Subscribe to channels ─────────────────────────────────────────────
    print(f"\n[INFO] Subscribing to {len(channel_names)} channel(s): {channel_names}")
    for ch in channel_names:
        tr_id = CHANNEL_TR_ID_MAP[ch]
        print(f"\n--- Channel: {ch} ({tr_id}) ---")
        _print_subscribe_payload_masked(tr_id, args.symbol, approval_key)

        try:
            client.subscribe(tr_id, args.symbol)
            print(f"  [OK] Subscribed to {tr_id}")
        except RuntimeError as e:
            print(f"  [WARN] Subscribe failed: {e}")

    # ── Simulate receiving messages (stub mode) ───────────────────────────
    if not args.real_ws:
        print("\n[INFO] Simulating message reception (stub mode)...")
        from kis.ws_parser import dispatch_message

        for ch in channel_names:
            tr_id = CHANNEL_TR_ID_MAP[ch]
            raw = json.dumps({
                "tr_id": tr_id,
                "MKSC_SHRN_ISCD": args.symbol,
            })
            result = dispatch_message(raw)
            print(f"\n--- {ch} ---")
            _print_parsed_summary(result)

    # ── Disconnect ────────────────────────────────────────────────────────
    client.disconnect()
    print("\n[OK] WebSocket disconnected")

    # ── Status ────────────────────────────────────────────────────────────
    status = client.get_status()
    print(f"\n[SUMMARY]")
    print(f"  mode: {'real-ws' if args.real_ws else 'stub'}")
    print(f"  symbol: {args.symbol}")
    print(f"  channels: {channel_names}")
    print(f"  duration: {args.duration}s" + (" (no limit)" if args.duration == 0 else ""))
    print(f"  max_messages: {args.max_messages}" + (" (no limit)" if args.max_messages == 0 else ""))
    print(f"  connection_state: {status.connection_state}")
    print(f"  subscribed_channels: {status.subscribed_channels}")
    print(f"  reconnect_count: {status.reconnect_count}")
    print(f"  data_quality_warnings: {status.data_quality_warnings}")
    print(f"\n[DONE] Smoke test completed successfully.")


if __name__ == "__main__":
    main()
