#!/usr/bin/env python3
"""SAT3 Opening Day Launcher — 9-step guided launch.

Usage:
  PYTHONPATH=./backend python backend/scripts/sat3_launcher.py [step]

Steps:
  1  preflight       Run preflight checks
  2  rest-smoke      REST read-only smoke test
  3  ws-smoke        WebSocket smoke test
  4  dashboard       Show dashboard URL
  5  dry-run         Dry-run pipeline
  6  safety-gate     SafetyGate check
  7  live-enable     Instructions for LIVE_TRADING_ENABLED=true
  8  confirm         Confirm live order (--dry-run first)
  9  start           Start automated trading
"""
from __future__ import annotations

import argparse
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

MASKED = "****-****-****"

STEPS = {
    "1": "preflight",
    "2": "rest-smoke",
    "3": "ws-smoke",
    "4": "dashboard",
    "5": "dry-run",
    "6": "safety-gate",
    "7": "live-enable",
    "8": "confirm",
    "9": "start",
}


def run_step(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Step: {name}")
    print(f"{'='*60}")

    if name == "preflight":
        from safety.preflight import run_preflight
        result = run_preflight()
        print(result.summary)
        if not result.passed:
            print("\n[FAIL] Preflight failed. Fix issues before proceeding.")
            sys.exit(1)
        print("\n[OK] Preflight passed.")

    elif name == "rest-smoke":
        script = os.path.join(BACKEND_DIR, "scripts", "kis_readonly_smoke.py")
        subprocess.run([sys.executable, script, "--real"], cwd=PROJECT_DIR)

    elif name == "ws-smoke":
        script = os.path.join(BACKEND_DIR, "scripts", "kis_ws_readonly_smoke.py")
        subprocess.run([sys.executable, script, "--real-ws"], cwd=PROJECT_DIR)

    elif name == "dashboard":
        print("Dashboard: cd frontend && npm run dev")
        print("Open http://localhost:5173 in browser")
        print("Verify: LIVE_TRADING_ENABLED=false, Emergency Stop inactive")
        print("Verify: WS CONNECTED, all cards populated")

    elif name == "dry-run":
        from runtime.orchestrator import Orchestrator
        from runtime.scheduler import SessionState
        orch = Orchestrator()
        result = orch.tick(SessionState.REGULAR_MARKET)
        print(f"Plan: {result['plan']}")
        print(f"Actions: {result['actions']}")
        live = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
        if live == "true":
            print("\n[WARN] LIVE_TRADING_ENABLED=true — this is NOT dry-run!")
        else:
            print("\n[OK] Dry-run complete. LIVE_TRADING_ENABLED=false → orders blocked.")

    elif name == "safety-gate":
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        live = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
        result = gate.check(
            live_trading_enabled=live,
            session="REGULAR_MARKET",
            market_regime="NORMAL",
            risk_approved=True,
        )
        print(f"SafetyGate: {'APPROVED' if result.passed else 'BLOCKED'}")
        for c in result.checks:
            status = "✓" if c.passed else "✗"
            print(f"  {status} {c.name}: {c.reason if not c.passed else 'OK'}")
        if not live:
            print("\n[INFO] LIVE_TRADING_ENABLED=false → BLOCKED (정상)")
            print("  Step 7에서 직접 .env를 수정하여 true로 변경하세요.")

    elif name == "live-enable":
        print("사용자가 직접 .env 파일을 수정해야 합니다:")
        print(f"  nano {os.path.join(PROJECT_DIR, '.env')}")
        print("  LIVE_TRADING_ENABLED=true 로 변경")
        print("  저장 후 Step 8로 진행")

    elif name == "confirm":
        live = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
        if live != "true":
            print("[BLOCKED] LIVE_TRADING_ENABLED is not true. Run Step 7 first.")
            sys.exit(1)
        print("[INFO] --confirm-live-order dry-run:")
        script = os.path.join(BACKEND_DIR, "scripts", "sat3_live_order_smoke.py")
        subprocess.run([sys.executable, script, "--confirm-live-order", "--dry-run"], cwd=PROJECT_DIR)
        print("\n[INFO] Dry-run 통과 시 --dry-run 제거하고 실제 실행 가능")

    elif name == "start":
        live = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
        if live != "true":
            print("[BLOCKED] LIVE_TRADING_ENABLED is not true.")
            sys.exit(1)
        print("[INFO] Starting automated trading...")
        from runtime.orchestrator import Orchestrator
        from runtime.scheduler import SessionState
        orch = Orchestrator()
        result = orch.tick(SessionState.REGULAR_MARKET)
        print(f"Result: {result}")


def main():
    parser = argparse.ArgumentParser(description="SAT3 Opening Day Launcher")
    parser.add_argument("step", nargs="?", choices=list(STEPS.keys()),
                        help="Step number (1-9) or name")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry run (default)")
    args = parser.parse_args()

    if args.step:
        name = STEPS.get(args.step, args.step)
        run_step(name)
    else:
        print("SAT3 Opening Day Launcher")
        print("Usage: python backend/scripts/sat3_launcher.py [1-9]")
        for num, name in STEPS.items():
            print(f"  {num}: {name}")


if __name__ == "__main__":
    main()
