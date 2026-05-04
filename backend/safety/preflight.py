"""Preflight Check — 운용 전 안전 점검"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    message: str
    detail: str = ""


@dataclass(frozen=True)
class PreflightResult:
    all_passed: bool
    checks: tuple[PreflightCheck, ...] = ()
    summary: str = ""


def _msg_or(condition: bool, ok_msg: str, fail_msg: str) -> str:
    return ok_msg if condition else fail_msg


def run_preflight(
    live_trading_enabled: bool,
    emergency_stop: bool,
    modules_loaded: bool,
    audit_writer_ok: bool,
    telegram_ok: bool,
    eod_report_ok: bool,
) -> PreflightResult:
    checks: list[PreflightCheck] = []

    checks.append(PreflightCheck(
        name="LIVE_TRADING_ENABLED",
        passed=True,
        message="WARNING: live trading is ENABLED" if live_trading_enabled
        else "OK: live trading disabled (safe mode)",
    ))

    checks.append(PreflightCheck(
        name="EMERGENCY_STOP",
        passed=True,
        message="WARNING: emergency stop is ACTIVE" if emergency_stop
        else "OK: emergency stop inactive",
    ))

    checks.append(PreflightCheck(
        name="MODULES_LOADED",
        passed=modules_loaded,
        message="OK: all modules loaded" if modules_loaded
        else "FAIL: modules not loaded",
    ))

    checks.append(PreflightCheck(
        name="AUDIT_WRITER",
        passed=audit_writer_ok,
        message="OK: audit writer operational" if audit_writer_ok
        else "FAIL: audit writer not available",
    ))

    checks.append(PreflightCheck(
        name="TELEGRAM_NOTIFIER",
        passed=telegram_ok,
        message="OK: Telegram notifier available" if telegram_ok
        else "WARN: Telegram notifier not available",
    ))

    checks.append(PreflightCheck(
        name="EOD_REPORT",
        passed=eod_report_ok,
        message="OK: EOD report builder ready" if eod_report_ok
        else "WARN: EOD report builder not ready",
    ))

    all_passed = all(c.passed for c in checks)
    summary_lines = [
        f"  [{c.name}] {'PASS' if c.passed else 'FAIL'}: {c.message}"
        for c in checks
    ]
    return PreflightResult(
        all_passed=all_passed,
        checks=tuple(checks),
        summary="\n".join(summary_lines),
    )
