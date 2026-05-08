from __future__ import annotations

import argparse
import asyncio
import os


def main() -> int:
    p = argparse.ArgumentParser(description="SAT3 LIVE AUTO trading guarded starter")
    p.add_argument("--confirm-live-auto-trading", required=True)
    p.add_argument("--confirm-account", required=True)
    p.add_argument("--max-daily-loss-krw", type=int, required=True)
    p.add_argument("--max-position-count", type=int, required=True)
    p.add_argument("--max-order-amount-krw", type=int, required=True)
    p.add_argument("--interval-sec", type=int, default=10)
    args = p.parse_args()

    if args.confirm_live_auto_trading != "CONFIRM_LIVE_AUTO_TRADING":
        print("START_BLOCKED: confirm string mismatch")
        return 2

    os.environ["SAT3_CONFIRM_LIVE_AUTO_TRADING"] = "CONFIRM_LIVE_AUTO_TRADING"
    os.environ["SAT3_MAX_DAILY_LOSS_KRW"] = str(args.max_daily_loss_krw)
    os.environ["SAT3_MAX_POSITION_COUNT"] = str(args.max_position_count)
    os.environ["SAT3_MAX_ORDER_AMOUNT_KRW"] = str(args.max_order_amount_krw)

    import main as backend_main

    payload = {
        "confirm": "CONFIRM_LIVE_AUTO_TRADING",
        "confirm_account": str(args.confirm_account or "").strip(),
        "max_daily_loss_krw": args.max_daily_loss_krw,
        "max_position_count": args.max_position_count,
        "max_order_amount_krw": args.max_order_amount_krw,
        "interval_sec": max(5, int(args.interval_sec)),
    }
    result = asyncio.run(backend_main.runtime_start_live(payload))
    started = bool(result.get("started", False))
    if started:
        print("LIVE_AUTO_START_ACCEPTED")
        return 0
    print(f"LIVE_AUTO_START_BLOCKED reason={result.get('reason','UNKNOWN')} block_reasons={result.get('block_reasons',[])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
