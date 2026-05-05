#!/usr/bin/env python3
"""SAT3 Emergency Stop CLI — activate/release/status.

Usage:
  PYTHONPATH=./backend python backend/scripts/sat3_emergency_stop_cli.py status
  PYTHONPATH=./backend python backend/scripts/sat3_emergency_stop_cli.py activate --reason "manual"
  PYTHONPATH=./backend python backend/scripts/sat3_emergency_stop_cli.py release --reason "checked"

Release does NOT mean orders are allowed — SafetyGate must still pass.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

STATE_FILE = os.path.join(PROJECT_DIR, ".emergency_stop")


def _read_state() -> dict:
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE) as f:
            lines = f.read().strip().split("\n")
        return {
            "active": lines[0] == "active" if lines else False,
            "reason": lines[1] if len(lines) > 1 else "",
            "timestamp": lines[2] if len(lines) > 2 else "",
        }
    return {"active": False, "reason": "", "timestamp": ""}


def _write_state(active: bool, reason: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        f.write(f"{'active' if active else 'inactive'}\n{reason}\n{ts}\n")


def cmd_status() -> None:
    state = _read_state()
    print(f"Emergency Stop: {'ACTIVE' if state['active'] else 'INACTIVE'}")
    if state["reason"]:
        print(f"  Reason: {state['reason']}")
    if state["timestamp"]:
        print(f"  Since: {state['timestamp']}")
    print("\nNote: release does NOT enable orders. SafetyGate still required.")


def cmd_activate(reason: str) -> None:
    _write_state(True, reason)
    print(f"Emergency Stop ACTIVATED: {reason}")
    print("All new orders and exit orders are now blocked.")


def cmd_release(reason: str) -> None:
    _write_state(False, reason)
    print(f"Emergency Stop RELEASED: {reason}")
    print("IMPORTANT: Orders remain blocked until SafetyGate passes.")
    print("Check SafetyGate before resuming trading.")


def main() -> int:
    parser = argparse.ArgumentParser(description="SAT3 Emergency Stop CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show emergency stop status")
    act = sub.add_parser("activate", help="Activate emergency stop")
    act.add_argument("--reason", default="manual", help="Reason for activation")
    rel = sub.add_parser("release", help="Release emergency stop")
    rel.add_argument("--reason", default="manual", help="Reason for release")
    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "activate":
        cmd_activate(args.reason)
    elif args.command == "release":
        cmd_release(args.reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
