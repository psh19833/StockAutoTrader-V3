#!/usr/bin/env python3
"""N17: Guarded small live order validation script.

Requires --confirm-live-order flag. Default is --dry-run.
"""
from __future__ import annotations

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="SAT3 Live Order Smoke Test")
    parser.add_argument("--confirm-live-order", action="store_true",
                        help="REQUIRED to submit real orders")
    parser.add_argument("--symbol", default="005930")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--side", default="buy", choices=["buy", "sell"])
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry run (default, no real orders)")
    args = parser.parse_args()

    # Safety checks
    live_enabled = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    if not live_enabled:
        print("BLOCKED: LIVE_TRADING_ENABLED=false")
        return

    if not args.confirm_live_order:
        print("BLOCKED: --confirm-live-order required")
        return

    if args.dry_run:
        print(f"DRY RUN: would {args.side} {args.qty} shares of {args.symbol}")
        print("No real order submitted.")
        return

    print("Real order submitted (simulated in test)")
