#!/usr/bin/env python3
"""SAT3 Preflight Check — local config & code health (no KIS calls).

Usage:
  PYTHONPATH=./backend python backend/scripts/sat3_preflight_check.py

Checks:
  - .env exists, required keys present (values NOT displayed)
  - LIVE_TRADING_ENABLED=false, or true with explicit live-auto-trading confirmation
  - SafetyGate defaults BLOCKED
  - Emergency Stop state
  - Module imports healthy
  - DB init capability
  - No secret leakage in output
"""
from __future__ import annotations

import os
import sys
import importlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

MASKED = "****-****-****"

REQUIRED_ENV_KEYS = [
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ACCOUNT_NO",
    "KIS_ACCOUNT_PRODUCT_CODE",
    "KIS_BASE_URL",
    "KIS_WEBSOCKET_URL",
]

REQUIRED_MODULES = [
    "kis.client",
    "kis.ws_client",
    "kis.order_api",
    "safety.live_order_safety_gate",
    "runtime.orchestrator",
    "runtime.scheduler",
    "dashboard.dashboard_models",
    "analytics.performance_analyzer",
]

results: list[tuple[str, str, str]] = []  # (check, status, detail)


def add(check: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    results.append((check, status, detail))


def main() -> int:
    print("=" * 60)
    print("SAT3 Preflight Check")
    print("=" * 60)

    # ── .env ─────────────────────────────────────────────────────────────
    env_path = os.path.join(PROJECT_DIR, ".env")
    env_exists = os.path.isfile(env_path)
    add(".env exists", env_exists, str(env_exists))

    if env_exists:
        # Load .env silently
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            add("dotenv import", False, "python-dotenv not installed")

        for key in REQUIRED_ENV_KEYS:
            val = os.getenv(key, "")
            add(f"  {key}", bool(val), "present" if val else "MISSING")
    else:
        for key in REQUIRED_ENV_KEYS:
            add(f"  {key}", False, ".env not found")

    # ── LIVE_TRADING_ENABLED ─────────────────────────────────────────────
    live_val = os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower()
    is_live = live_val in ("true", "1", "yes")
    live_confirmed = os.getenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", "") == "CONFIRM_LIVE_AUTO_TRADING"
    live_ok = (not is_live) or live_confirmed
    add("LIVE_TRADING_ENABLED", live_ok,
        "false (safe)" if not is_live else (
            "true (explicit confirmation present)" if live_confirmed else "WARNING: true without explicit confirmation"
        ))

    # ── Emergency Stop ───────────────────────────────────────────────────
    em_stop_path = os.path.join(PROJECT_DIR, ".emergency_stop")
    em_active = os.path.isfile(em_stop_path)
    add("Emergency Stop", not em_active,
        "inactive" if not em_active else "ACTIVE — all orders blocked")

    # ── Module imports ───────────────────────────────────────────────────
    import_errors = []
    for mod in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
        except Exception as e:
            import_errors.append(f"{mod}: {e}")
    add("Module imports", len(import_errors) == 0,
        f"{len(REQUIRED_MODULES) - len(import_errors)}/{len(REQUIRED_MODULES)} OK"
        if not import_errors else "; ".join(import_errors[:3]))

    # ── SafetyGate default ───────────────────────────────────────────────
    try:
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        result = gate.check(
            live_trading_enabled=False, session="REGULAR_MARKET",
            market_regime="NORMAL", risk_approved=True,
        )
        add("SafetyGate default", not result.passed,
            "BLOCKED (LIVE_TRADING_ENABLED=false)" if not result.passed else "UNEXPECTED APPROVED")
    except Exception as e:
        add("SafetyGate default", False, str(e))

    # ── Order API guarded ────────────────────────────────────────────────
    try:
        from kis.order_api import submit_cash_order
        r = submit_cash_order("005930", "buy", 1, safety_gate_approved=False, live_trading_enabled=False)
        add("Order API guarded", not r.success, f"blocked: {r.message}")
    except Exception as e:
        add("Order API guarded", False, str(e))

    # ── WS client: approval_key guard is enforced before any network ───────
    try:
        from kis.ws_client import GuardedRealWebSocketClient
        client = GuardedRealWebSocketClient()
        try:
            client.connect(approval_key="", base_url="ws://dummy")
            add("WS real client requires approval_key", False, "UNEXPECTED: connect succeeded")
        except ValueError:
            add("WS real client requires approval_key", True, "ValueError raised without approval_key")
        except Exception as e:
            add(
                "WS real client requires approval_key",
                False,
                f"Unexpected exception: {type(e).__name__}: {e}",
            )
    except Exception as e:
        add("WS real client requires approval_key", False, f"import/connect check failed: {e}")

    # ── Frontend ─────────────────────────────────────────────────────────
    fe_path = os.path.join(PROJECT_DIR, "frontend", "package.json")
    fe_exists = os.path.isfile(fe_path)
    add("Frontend package.json", fe_exists, str(fe_exists))

    # ── DB Path ──────────────────────────────────────────────────────────
    db_path = os.getenv("SAT3_DB_PATH", os.path.join(PROJECT_DIR, "data", "sat3.db"))
    db_dir = os.path.dirname(db_path)
    add("DB directory", os.path.isdir(db_dir) or os.path.isdir(os.path.dirname(db_dir)),
        db_path)

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    for check, status, detail in results:
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {check}: {detail}")

    print(f"\n{'='*60}")
    print(f"  Total: {passed} passed, {failed} failed")
    if failed == 0:
        print("  RESULT: ALL CHECKS PASSED")
    else:
        print("  RESULT: SOME CHECKS FAILED — fix before market open")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
