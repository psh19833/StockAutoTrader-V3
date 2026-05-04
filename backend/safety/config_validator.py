"""Config Validator — 설정 검증"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigValidationResult:
    passed: bool
    message: str
    detail: str = ""


def mask_sensitive_value(value: str) -> str:
    if len(value) <= 2:
        return "**"
    return value[:4] + "****"


def validate_live_trading_enabled(enabled: bool) -> ConfigValidationResult:
    if enabled:
        return ConfigValidationResult(
            passed=True,
            message="WARNING: LIVE_TRADING_ENABLED=true (live orders possible)",
        )
    return ConfigValidationResult(
        passed=True,
        message="OK: LIVE_TRADING_ENABLED=false (default safe mode)",
    )


def validate_required_modules(modules: list[str]) -> ConfigValidationResult:
    import importlib
    missing = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return ConfigValidationResult(
            passed=False,
            message=f"Missing modules: {', '.join(missing)}",
        )
    return ConfigValidationResult(
        passed=True,
        message=f"All {len(modules)} required modules present",
    )
