#!/usr/bin/env python3
"""SAT3 Dashboard Health Check — local state only, no external calls.

Usage:
  PYTHONPATH=./backend python backend/scripts/sat3_dashboard_health_check.py
"""
from __future__ import annotations

import os
import sys
import importlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

results = []


def add(check: str, ok: bool, detail: str = "") -> None:
    results.append((check, "PASS" if ok else "FAIL", detail))


def main() -> int:
    print("=" * 60)
    print("SAT3 Dashboard Health Check")
    print("=" * 60)

    # Backend modules
    for mod in ["dashboard.dashboard_models", "dashboard.dashboard_service"]:
        try:
            importlib.import_module(mod)
            add(f"Import {mod}", True)
        except Exception as e:
            add(f"Import {mod}", False, str(e))

    # Dashboard models contain required views
    try:
        from dashboard.dashboard_models import (
            SystemStatusView, WebSocketStatusView, DataRouterStatusView,
            DashboardSummary,
        )
        add("Dashboard views", True, "SystemStatus, WSStatus, DataRouter, Summary")
    except Exception as e:
        add("Dashboard views", False, str(e))

    # No order buttons in dashboard models
    try:
        from dashboard.dashboard_models import WebSocketStatusView
        attrs = dir(WebSocketStatusView)
        forbidden = ["buy", "sell", "order", "execute", "toggle_live"]
        found = [a for a in attrs if any(f in a.lower() for f in forbidden)]
        add("Dashboard no order fields", len(found) == 0,
            f"found: {found}" if found else "clean")
    except Exception as e:
        add("Dashboard no order fields", False, str(e))

    # Frontend
    fe_path = os.path.join(PROJECT_DIR, "frontend")
    pkg_path = os.path.join(fe_path, "package.json")
    add("Frontend package.json", os.path.isfile(pkg_path))

    dist_path = os.path.join(fe_path, "dist", "index.html")
    add("Frontend build", os.path.isfile(dist_path),
        "dist exists" if os.path.isfile(dist_path) else "run: cd frontend && npm run build")

    # No LIVE toggle in frontend
    for check_file in ["DashboardPage.jsx", "SystemStatusCard.jsx"]:
        fp = os.path.join(fe_path, "src", "pages" if "Page" in check_file else "components/dashboard", check_file)
        if os.path.isfile(fp):
            with open(fp) as f:
                content = f.read()
            has_toggle = "toggle" in content.lower() and "live" in content.lower()
            add(f"FE {check_file} no LIVE toggle", not has_toggle,
                "has toggle!" if has_toggle else "clean")

    # Print results
    print()
    for check, status, detail in results:
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {check}: {detail}")

    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"\n{'='*60}")
    print(f"  {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
