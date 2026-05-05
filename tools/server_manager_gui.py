#!/usr/bin/env python3
"""
Tkinter-based GUI wrapper for Stock Auto Trader Ver. 3.0 server manager.

Reuses the public API from tools/server_manager.py for all server operations.
Safe: no trading logic access, no .env modification.

Usage:
  python tools/server_manager_gui.py

Windows shortcut:
  C:\\Windows\\System32\\wsl.exe -d Ubuntu --cd /home/psh19/StockAutoTrader-V3 -- python3 tools/server_manager_gui.py
"""
from __future__ import annotations

import os
import sys
import threading

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from tools.server_manager import (
    LOG_FILES, get_log_content, get_status,
    restart_all, restart_backend, restart_frontend,
    start_all, start_backend, start_frontend,
    stop_all, stop_backend, stop_frontend,
)

_WINDOW_TITLE = "SAT3 — Stock Auto Trader Server Manager"
_WINDOW_GEOMETRY = "860x620"
_REFRESH_INTERVAL_MS = 5000

_BACKEND_URL = "http://127.0.0.1:8000"
_FRONTEND_URL = "http://127.0.0.1:5173"
_DOCS_URL = "http://127.0.0.1:8000/docs"

_BG_LIGHT = "#f5f5f5"
_FG_RUNNING = "#1b8a1b"
_FG_STOPPED = "#aa2222"
_BTN_WIDTH = 16


def _open_url(url: str) -> None:
    import subprocess
    try:
        if os.name == "nt":
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        pass


class ServerManagerGUI:
    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title(_WINDOW_TITLE)
        self._root.geometry(_WINDOW_GEOMETRY)
        self._root.resizable(True, True)
        self._root.configure(bg=_BG_LIGHT)
        self._root.minsize(700, 500)
        self._action_running = False
        self._buttons: Dict[str, tk.Widget] = {}
        self._build_ui()
        self._refresh_status()
        self._schedule_auto_refresh()

    def _build_ui(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        main_frame = ttk.Frame(self._root, padding=12)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        title = ttk.Label(main_frame, text="Stock Auto Trader v3 — Server Manager",
                          font=("Segoe UI", 14, "bold"), anchor="center")
        title.grid(row=0, column=0, pady=(0, 12), sticky="ew")

        cards_frame = ttk.Frame(main_frame)
        cards_frame.grid(row=1, column=0, pady=(0, 10), sticky="ew")
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)

        self._backend_card = self._build_card(cards_frame, 0, "Backend", _BACKEND_URL,
                                              _DOCS_URL, "btn_backend_start", "btn_backend_stop",
                                              "btn_backend_restart", "btn_backend_docs")
        self._frontend_card = self._build_card(cards_frame, 1, "Frontend", _FRONTEND_URL,
                                               _FRONTEND_URL, "btn_frontend_start", "btn_frontend_stop",
                                               "btn_frontend_restart", "btn_frontend_app")

        controls = ttk.Frame(main_frame)
        controls.grid(row=2, column=0, pady=(0, 8), sticky="ew")
        for text, action in [("Start All", "start_all"), ("Stop All", "stop_all"),
                             ("Restart All", "restart_all")]:
            self._buttons[f"btn_global_{action}"] = ttk.Button(
                controls, text=text, command=lambda a=action: self._threaded(a), width=12)
            self._buttons[f"btn_global_{action}"].pack(side="left", padx=3)
        ttk.Button(controls, text="Refresh", command=self._refresh_status, width=12).pack(side="left", padx=3)

        log_frame = ttk.LabelFrame(main_frame, text="Log Viewer", padding=6)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        log_tabs = ttk.Frame(log_frame)
        log_tabs.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        for log_name in LOG_FILES:
            ttk.Button(log_tabs, text=log_name.replace("_server.log", "").replace("_", " ").title(),
                       command=lambda n=log_name: self._show_log(n)).pack(side="left", padx=2)
        self._log_text = tk.Text(log_frame, height=10, wrap="word", font=("Consolas", 9),
                                 bg="#1e1e1e", fg="#d4d4d4", state="disabled")
        self._log_text.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self._log_text.configure(yscrollcommand=scroll.set)
        self._current_log: Optional[str] = None
        self._show_log("server_manager.log")

        self._footer = ttk.Label(main_frame, text="Ready", font=("Segoe UI", 9),
                                 anchor="w", relief="sunken", padding=4)
        self._footer.grid(row=4, column=0, sticky="ew", pady=(6, 0))

    def _build_card(self, parent, col, title, url, open_url_target, bk, bkk, bkkk, bk4):
        card = ttk.LabelFrame(parent, text=title, padding=10)
        card.grid(row=0, column=col, sticky="nsew", padx=4)
        sf = ttk.Frame(card); sf.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(sf, text="Status:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        sl = ttk.Label(sf, text="Checking...", font=("Segoe UI", 10))
        sl.grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Label(card, text=url, font=("Consolas", 9), foreground="#555555").grid(row=1, column=0, sticky="w", pady=(0, 8))
        pf = ttk.Frame(card); pf.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(pf, text="PID:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        pl = ttk.Label(pf, text="-", font=("Consolas", 9)); pl.grid(row=0, column=1, sticky="w", padx=(6, 0))
        bf = ttk.Frame(card); bf.grid(row=3, column=0, sticky="ew")
        bi = ttk.Frame(bf); bi.grid(row=0, column=0)
        is_backend = "backend" in title.lower()
        btn_start = ttk.Button(bi, text="Start", width=_BTN_WIDTH,
                               command=lambda: self._threaded("start_backend" if is_backend else "start_frontend"))
        btn_start.pack(side="left", padx=2)
        btn_stop = ttk.Button(bi, text="Stop", width=_BTN_WIDTH,
                              command=lambda: self._threaded("stop_backend" if is_backend else "stop_frontend"))
        btn_stop.pack(side="left", padx=2)
        btn_restart = ttk.Button(bi, text="Restart", width=_BTN_WIDTH,
                                 command=lambda: self._threaded("restart_backend" if is_backend else "restart_frontend"))
        btn_restart.pack(side="left", padx=2)
        btn_open = ttk.Button(bi, text="Open Docs" if is_backend else "Open App", width=_BTN_WIDTH,
                              command=lambda u=open_url_target: _open_url(u))
        btn_open.pack(side="left", padx=2)
        self._buttons[bk], self._buttons[bkk], self._buttons[bkkk], self._buttons[bk4] = btn_start, btn_stop, btn_restart, btn_open
        return {"status_label": sl, "pid_label": pl}

    def _threaded(self, action: str) -> None:
        if self._action_running: return
        self._action_running = True
        self._set_buttons_state("disabled")
        threading.Thread(target=self._run_action, args=(action,), daemon=True).start()

    def _run_action(self, action: str) -> None:
        action_map: Dict[str, Callable[[], bool]] = {
            "start_backend": start_backend, "stop_backend": stop_backend, "restart_backend": restart_backend,
            "start_frontend": start_frontend, "stop_frontend": stop_frontend, "restart_frontend": restart_frontend,
            "start_all": start_all, "stop_all": stop_all, "restart_all": restart_all,
        }
        fn = action_map.get(action)
        result = fn() if fn else False
        self._root.after(0, self._on_action_done, result)

    def _on_action_done(self, result: bool) -> None:
        self._action_running = False
        self._set_buttons_state("normal")
        self._refresh_status()
        if self._current_log:
            self._show_log(self._current_log)

    def _set_buttons_state(self, state: str) -> None:
        for key, widget in self._buttons.items():
            if "docs" in key or "app" in key: continue
            try: widget.configure(state=state)
            except tk.TclError: pass
        self._root.update_idletasks()

    def _refresh_status(self) -> None:
        try:
            s = get_status()
            for card, key in [(self._backend_card, "backend"), (self._frontend_card, "frontend")]:
                info = s[key]
                running = info["running"]
                pid = info["pid"][0] if info["pid"] else None
                card["status_label"].configure(text="RUNNING" if running else "STOPPED",
                                               foreground=_FG_RUNNING if running else _FG_STOPPED)
                card["pid_label"].configure(text=str(pid) if pid else "-")
        except Exception: pass

    def _schedule_auto_refresh(self) -> None:
        if not self._action_running: self._refresh_status()
        self._root.after(_REFRESH_INTERVAL_MS, self._schedule_auto_refresh)

    def _show_log(self, log_name: str) -> None:
        self._current_log = log_name
        content = get_log_content(log_name, max_lines=40)
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.insert("1.0", content)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def run(self) -> None:
        self._root.mainloop()


def main() -> None:
    ServerManagerGUI().run()


if __name__ == "__main__":
    main()
