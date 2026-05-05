#!/usr/bin/env python3
"""SAT3 Market Open Launcher — guided market open workflow.

Usage:
  PYTHONPATH=./backend python backend/scripts/sat3_market_open_launcher.py [step]
  PYTHONPATH=./backend python backend/scripts/sat3_market_open_launcher.py --auto --confirm-live-order --dry-run

Options:
  --dry-run                Default true. No real orders.
  --confirm-live-order     Required for live orders.
  --skip-rest-smoke        Skip REST smoke check.
  --skip-ws-smoke          Skip WebSocket smoke check.
  --start-auto-trading     Start auto trading (requires confirm + SafetyGate).
  --symbol 005930          Symbol for smoke tests.
  --max-runtime-minutes N  Max runtime.
  --once                   Run once then exit.

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
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

MASKED = "****-****-****"


STEPS = {
    "1": "preflight", "2": "rest-smoke", "3": "ws-smoke",
    "4": "dashboard", "5": "dry-run", "6": "safety-gate",
    "7": "live-enable", "8": "confirm", "9": "start",
}


def banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def run_preflight() -> int:
    banner("Step 1: Preflight")
    script = os.path.join(BACKEND_DIR, "scripts", "sat3_preflight_check.py")
    return subprocess.run([sys.executable, script], cwd=PROJECT_DIR).returncode


def run_rest_smoke(symbol: str) -> None:
    banner("Step 2: REST Read-Only Smoke")
    print("[INFO] This step requires KIS API access (market open day).")
    script = os.path.join(BACKEND_DIR, "scripts", "kis_readonly_smoke.py")
    subprocess.run([sys.executable, script, "--real", "--debug-keys"], cwd=PROJECT_DIR)


def run_ws_smoke(symbol: str) -> None:
    banner("Step 3: WebSocket Smoke")
    print("[INFO] This step requires KIS WebSocket access (market open day).")
    script = os.path.join(BACKEND_DIR, "scripts", "kis_ws_readonly_smoke.py")
    subprocess.run([sys.executable, script, "--real-ws", f"--symbol={symbol}"], cwd=PROJECT_DIR)


def run_dashboard_check() -> None:
    banner("Step 4: Dashboard Check")
    script = os.path.join(BACKEND_DIR, "scripts", "sat3_dashboard_health_check.py")
    rc = subprocess.run([sys.executable, script], cwd=PROJECT_DIR).returncode
    print("\nDashboard: cd frontend && npm run dev")
    print("Open http://localhost:5173 — verify all cards populated.")


def run_dry_run() -> None:
    banner("Step 5: Dry-Run Pipeline")
    from runtime.orchestrator import Orchestrator
    from runtime.scheduler import SessionState
    orch = Orchestrator()
    result = orch.tick(SessionState.REGULAR_MARKET, mode="dry-run")
    print(f"Plan: {result['plan']}")
    print(f"Actions: {result['actions']}")
    live = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
    if live == "true":
        print("\n[WARN] LIVE_TRADING_ENABLED=true — this IS live!")
    else:
        print("\n[OK] Dry-run complete. Orders blocked (LIVE_TRADING_ENABLED=false).")


def run_safety_gate() -> None:
    banner("Step 6: SafetyGate Check")
    from safety.live_order_safety_gate import LiveOrderSafetyGate
    gate = LiveOrderSafetyGate()
    # Check emergency stop
    em_path = os.path.join(PROJECT_DIR, ".emergency_stop")
    if os.path.isfile(em_path):
        with open(em_path) as f:
            gate.emergency_stop = f.readline().strip() == "active"
    live = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    result = gate.check(
        live_trading_enabled=live, session="REGULAR_MARKET",
        market_regime="NORMAL", risk_approved=True,
    )
    print(f"SafetyGate: {'APPROVED' if result.passed else 'BLOCKED'}")
    for c in result.checks:
        status = "✓" if c.passed else "✗"
        print(f"  {status} {c.name}: {c.reason if not c.passed else 'OK'}")


def run_live_enable() -> None:
    banner("Step 7: LIVE_TRADING_ENABLED=true (Manual)")
    print("사용자가 직접 .env 파일을 수정해야 합니다:")
    print(f"  nano {os.path.join(PROJECT_DIR, '.env')}")
    print("  LIVE_TRADING_ENABLED=true 로 변경 후 저장")


def run_confirm(args: argparse.Namespace) -> None:
    banner("Step 8: Confirm Live Order")
    live = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
    if live != "true":
        print("[BLOCKED] LIVE_TRADING_ENABLED is not true. Run Step 7 first.")
        return
    script = os.path.join(BACKEND_DIR, "scripts", "sat3_live_order_smoke.py")
    cmd = [sys.executable, script, "--confirm-live-order", f"--symbol={args.symbol}"]
    if args.dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, cwd=PROJECT_DIR)


def run_start(args: argparse.Namespace) -> None:
    banner("Step 9: Live Trading Start (Safety Phase)")
    live = os.getenv("LIVE_TRADING_ENABLED", "false").lower()
    if live != "true":
        print("[BLOCKED] LIVE_TRADING_ENABLED is not true.")
        return
    if not args.confirm_live_order:
        print("[BLOCKED] --confirm-live-order required.")
        return
    print("[INFO] Starting LIVE mode tick (safety phase)...")
    print("[INFO] No real order submitted in this Phase.")

    from runtime.orchestrator import Orchestrator
    from runtime.scheduler import SessionState
    orch = Orchestrator()

    try:
        result = orch.tick(SessionState.REGULAR_MARKET, mode="live")
        live_result = result.get("live", {})
        status = (live_result or {}).get("status", "")
        reason = (live_result or {}).get("reason", "")
        print(f"Tick result: mode=live status={status} reason={reason}")

        if status in ("BLOCKED_NOT_CONFIGURED", "BLOCKED_NOT_IMPLEMENTED"):
            print("[BLOCKED] LIVE_TRADING_RUNNER_NOT_READY / submitter not configured")
            print("          Dry-run pipeline is NOT live trading.")
            return

        # Placeholder monitor loop (should not imply trading is running)
        if not args.once:
            print("[INFO] Monitor loop placeholder (no trading loop implemented). Press Ctrl+C to exit.")
            start_time = time.time()
            max_seconds = (args.max_runtime_minutes or 0) * 60
            while True:
                time.sleep(5)
                if max_seconds and (time.time() - start_time) > max_seconds:
                    print(f"[INFO] Max runtime ({args.max_runtime_minutes}m) reached.")
                    break
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted. Stopping.")
    finally:
        orch.stop()
        print("[OK] Runner stopped.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SAT3 Market Open Launcher")
    parser.add_argument("step", nargs="?", choices=list(STEPS.keys()),
                        help="Step number (1-9)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry run — no real orders")
    parser.add_argument("--confirm-live-order", action="store_true",
                        help="EXPLICIT confirmation for live orders")
    parser.add_argument("--skip-rest-smoke", action="store_true")
    parser.add_argument("--skip-ws-smoke", action="store_true")
    parser.add_argument("--symbol", default="005930")
    parser.add_argument("--max-runtime-minutes", type=int, default=0)
    parser.add_argument("--once", action="store_true",
                        help="Run once then exit")
    parser.add_argument("--start-auto-trading", action="store_true",
                        help="Start auto trading (step 9)")
    args = parser.parse_args()

    if args.start_auto_trading:
        run_start(args)
        return

    if args.step:
        step_map = {
            "1": lambda: run_preflight(),
            "2": lambda: run_rest_smoke(args.symbol) if not args.skip_rest_smoke else None,
            "3": lambda: run_ws_smoke(args.symbol) if not args.skip_ws_smoke else None,
            "4": run_dashboard_check,
            "5": run_dry_run,
            "6": run_safety_gate,
            "7": run_live_enable,
            "8": lambda: run_confirm(args),
            "9": lambda: run_start(args),
        }
        fn = step_map.get(args.step)
        if fn:
            fn()
    else:
        print("SAT3 Market Open Launcher")
        for num, name in STEPS.items():
            print(f"  {num}: {name}")
        print("\nUsage: python backend/scripts/sat3_market_open_launcher.py [1-9]")


if __name__ == "__main__":
    main()
