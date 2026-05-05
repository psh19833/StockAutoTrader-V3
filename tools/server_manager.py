#!/usr/bin/env python3
"""
Local development server manager for Stock Auto Trader Ver. 3.0.

Features:
  - Check backend (port 8000) and frontend (port 5173) status
  - Start/stop/restart backend and frontend servers
  - Log output to logs/ directory
  - WSL UNC path guard (Windows Python accessing \\\\wsl.localhost)

Usage:
  python tools/server_manager.py          # interactive menu
  python tools/server_manager.py --check  # one-shot status check only

Requires: Python 3.8+, standard library only.
"""
from __future__ import annotations

import os
import platform
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load .env before anything else
try:
    from dotenv import load_dotenv
    _env_path = _PROJECT_ROOT / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _PROJECT_ROOT / "backend"
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"
_LOGS_DIR = _PROJECT_ROOT / "logs"

_PROJECT_ROOT_STR: str = str(_PROJECT_ROOT)
_WSL_UNC_PREFIXES: Tuple[str, ...] = (r"\\wsl.localhost", r"\\wsl$")
_IS_WSL_UNC_PATH: bool = any(_PROJECT_ROOT_STR.startswith(p) for p in _WSL_UNC_PREFIXES)

_BACKEND_PORT = 8000
_FRONTEND_PORT = 5173
_BACKEND_URL = "http://127.0.0.1:8000"
_FRONTEND_URL = "http://127.0.0.1:5173"

_LOG_BACKEND = "backend_server.log"
_LOG_FRONTEND = "frontend_server.log"
_LOG_MANAGER = "server_manager.log"

LOG_FILES = [_LOG_BACKEND, _LOG_FRONTEND, _LOG_MANAGER]

_backend_proc: Optional[subprocess.Popen] = None
_frontend_proc: Optional[subprocess.Popen] = None


def _ensure_logs_dir() -> None:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _log(msg: str, file: str = _LOG_MANAGER) -> None:
    _ensure_logs_dir()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(_LOGS_DIR / file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _pids_on_port(port: int) -> List[int]:
    try:
        r = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return [int(p) for p in r.stdout.strip().split()]
    except Exception:
        pass
    return []


def _stop_port(port: int, label: str) -> bool:
    if not _port_is_open(port):
        return True
    pids = _pids_on_port(port)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    time.sleep(1)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
    time.sleep(0.5)
    return not _port_is_open(port)


def get_status() -> Dict:
    return {
        "backend": {"running": _port_is_open(_BACKEND_PORT), "pid": _pids_on_port(_BACKEND_PORT)[:1] or [None]},
        "frontend": {"running": _port_is_open(_FRONTEND_PORT), "pid": _pids_on_port(_FRONTEND_PORT)[:1] or [None]},
    }


def get_log_content(log_name: str, max_lines: int = 40) -> str:
    path = _LOGS_DIR / log_name
    if not path.exists():
        return f"(no log file: {path})"
    # Handle non-UTF8 bytes from npm/ansi output
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _send_telegram_startup() -> None:
    """Send Telegram notification on backend startup."""
    try:
        import json, urllib.request
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            return
        body = json.dumps({
            "chat_id": chat_id,
            "text": "ℹ️ <b>🚀 SAT3 서버 시작</b>\nSAT3 백엔드 서버가 시작되었습니다.",
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def start_backend() -> bool:
    global _backend_proc

    # Telegram notification — always send on start attempt
    _send_telegram_startup()

    if _port_is_open(_BACKEND_PORT):
        print(f"  Backend already running on port {_BACKEND_PORT}")
        return True
    _ensure_logs_dir()
    log_path = _LOGS_DIR / _LOG_BACKEND
    venv_python = str(_PROJECT_ROOT / ".venv" / "bin" / "python")

    print(f"  Starting backend: uvicorn main:app --host 127.0.0.1 --port {_BACKEND_PORT}")
    _log("start_backend: starting...")
    log_fh = open(log_path, "a", encoding="utf-8")
    try:
        env = {**os.environ, "PYTHONPATH": str(_BACKEND_DIR)}
        _backend_proc = subprocess.Popen(
            [venv_python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(_BACKEND_PORT)],
            cwd=str(_BACKEND_DIR), env=env,
            stdout=log_fh, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as e:
        log_fh.close()
        print(f"  ERROR: {e}")
        _log(f"start_backend: FAILED — {e}")
        return False
    for _ in range(30):
        if _port_is_open(_BACKEND_PORT):
            print(f"  Backend started (PID {_backend_proc.pid}) → {_BACKEND_URL}")
            _log(f"start_backend: PID {_backend_proc.pid}")
            return True
        time.sleep(0.5)
    print(f"  Backend failed to start. Check: {log_path}")
    return False


def stop_backend() -> bool:
    print(f"  Stopping backend (port {_BACKEND_PORT})...")
    return _stop_port(_BACKEND_PORT, "backend")


def restart_backend() -> bool:
    stop_backend()
    time.sleep(1)
    return start_backend()


def start_frontend() -> bool:
    global _frontend_proc

    # ── WSL UNC path guard ──────────────────────────────────────────────
    if _IS_WSL_UNC_PATH:
        print("  ERROR: Project path is a WSL UNC path. Launch from inside WSL instead.")
        print(f"    wsl -d Ubuntu --cd /home/psh19/StockAutoTrader-V3 -- python3 tools/server_manager_gui.py")
        _log("start_frontend: BLOCKED — UNC path detected")
        return False

    if _port_is_open(_FRONTEND_PORT):
        print(f"  Frontend already running on port {_FRONTEND_PORT}")
        return True
    _ensure_logs_dir()
    log_path = _LOGS_DIR / _LOG_FRONTEND
    print(f"  Starting frontend: npm run dev (port {_FRONTEND_PORT})")
    _log("start_frontend: starting...")
    log_fh = open(log_path, "a", encoding="utf-8")
    try:
        cmd = f"cd '{_FRONTEND_DIR}' && npm run dev -- --host 127.0.0.1 --port {_FRONTEND_PORT}"
        _frontend_proc = subprocess.Popen(
            ["/bin/bash", "-lc", cmd],
            stdout=log_fh, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as e:
        log_fh.close()
        print(f"  ERROR: {e}")
        _log(f"start_frontend: FAILED — {e}")
        return False
    for _ in range(40):
        if _port_is_open(_FRONTEND_PORT):
            print(f"  Frontend started (PID {_frontend_proc.pid}) → {_FRONTEND_URL}")
            _log(f"start_frontend: PID {_frontend_proc.pid}")
            return True
        time.sleep(0.5)
    print(f"  Frontend failed to start. Check: {log_path}")
    _log("start_frontend: FAILED — timeout")
    return False


def stop_frontend() -> bool:
    print(f"  Stopping frontend (port {_FRONTEND_PORT})...")
    return _stop_port(_FRONTEND_PORT, "frontend")


def restart_frontend() -> bool:
    stop_frontend()
    time.sleep(1)
    return start_frontend()


def start_all() -> bool:
    b = start_backend()
    f = start_frontend()
    return b and f


def stop_all() -> bool:
    return stop_backend() and stop_frontend()


def restart_all() -> bool:
    stop_all()
    time.sleep(2)
    return start_all()


def interactive_menu() -> None:
    while True:
        s = get_status()
        be = "RUNNING" if s["backend"]["running"] else "STOPPED"
        fe = "RUNNING" if s["frontend"]["running"] else "STOPPED"
        print(f"\n=== SAT3 Server Manager ===\n  Backend  ({_BACKEND_URL}): {be}\n  Frontend ({_FRONTEND_URL}): {fe}")
        print("  1) Start All  2) Stop All  3) Restart All")
        print("  4) Start Backend  5) Stop Backend  6) Restart Backend")
        print("  7) Start Frontend 8) Stop Frontend 9) Restart Frontend")
        print("  0) Exit")
        choice = input("  > ").strip()
        actions = {
            "1": start_all, "2": stop_all, "3": restart_all,
            "4": start_backend, "5": stop_backend, "6": restart_backend,
            "7": start_frontend, "8": stop_frontend, "9": restart_frontend,
        }
        if choice == "0":
            break
        fn = actions.get(choice)
        if fn:
            fn()
        else:
            print("  Invalid choice")


if __name__ == "__main__":
    if "--check" in sys.argv:
        s = get_status()
        print(f"backend: {'RUNNING' if s['backend']['running'] else 'STOPPED'}")
        print(f"frontend: {'RUNNING' if s['frontend']['running'] else 'STOPPED'}")
    else:
        interactive_menu()
