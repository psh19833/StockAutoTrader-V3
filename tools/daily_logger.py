"""Daily log system — date-segmented, category-based operational logs.

Usage:
  from tools.daily_logger import DailyLogger, LogCategory

  logger = DailyLogger()
  logger.log(LogCategory.TRADING, "order submitted: 005930 BUY 10")
  logger.get_logs("2026-05-06", LogCategory.TRADING)  # returns list[str]
  logger.get_available_dates()  # returns list[str]
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class LogCategory(str, Enum):
    TRADING = "trading"
    SCANNER = "scanner"
    QUANT = "quant"
    RISK = "risk"
    SYSTEM = "system"
    WEBSOCKET = "websocket"
    TELEGRAM = "telegram"
    EMERGENCY = "emergency"


# Secret patterns to filter from logs
_SECRET_FILTERS = ["appkey=", "appsecret=", "access_token=", "approval_key=",
                   "APP_KEY=", "APP_SECRET=", "ACCESS_TOKEN=", "APPROVAL_KEY="]

_LOGS_ROOT = Path(__file__).resolve().parents[2] / "logs"


def _filter_secrets(line: str) -> str:
    """Replace secret values with *** in log lines."""
    result = line
    for pattern in _SECRET_FILTERS:
        if pattern in result.lower():
            idx = result.lower().find(pattern)
            end = len(result)
            for c in " \n\t\r,;":
                pos = result.find(c, idx + len(pattern))
                if pos != -1:
                    end = pos
                    break
            result = result[:idx + len(pattern)] + "***" + result[end:]
    return result


class DailyLogger:
    """Date-segmented, category-based logger."""

    def __init__(self, logs_root: Optional[Path] = None):
        self._root = logs_root or _LOGS_ROOT
        self._today: Optional[str] = None

    def _today_str(self) -> str:
        if self._today:
            return self._today
        return date.today().isoformat()

    def set_today(self, date_str: str) -> None:
        """Override today's date (for testing)."""
        self._today = date_str

    def _category_path(self, date_str: str, category: LogCategory) -> Path:
        return self._root / date_str / f"{category.value}.log"

    def log(self, category: LogCategory, message: str) -> None:
        """Append a message to the log for today's date."""
        today = self._today_str()
        path = self._category_path(today, category)
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        filtered = _filter_secrets(message)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {filtered}\n")

    def get_logs(self, date_str: str, category: LogCategory,
                 max_lines: int = 100, tail: bool = True) -> list[str]:
        """Read log lines for a specific date and category."""
        path = self._category_path(date_str, category)
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.rstrip() for line in f.readlines()]
        if tail:
            lines = lines[-max_lines:]
        else:
            lines = lines[:max_lines]
        return lines

    def get_available_dates(self) -> list[str]:
        """Return sorted list of dates with log data."""
        if not self._root.exists():
            return []
        dates = []
        for entry in sorted(self._root.iterdir(), reverse=True):
            if entry.is_dir():
                try:
                    date.fromisoformat(entry.name)
                    dates.append(entry.name)
                except ValueError:
                    pass
        return dates

    def get_available_categories(self, date_str: str) -> list[str]:
        """Return categories that have logs for a given date."""
        date_dir = self._root / date_str
        if not date_dir.exists():
            return []
        cats = []
        for cat in LogCategory:
            if (date_dir / f"{cat.value}.log").exists():
                cats.append(cat.value)
        return cats
