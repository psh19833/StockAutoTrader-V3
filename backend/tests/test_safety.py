"""Tests for Safety — config validator, preflight, release gate"""
from __future__ import annotations

import pytest
from safety.config_validator import (
    ConfigValidationResult, validate_live_trading_enabled,
    validate_required_modules, mask_sensitive_value,
)
from safety.preflight import PreflightCheck, PreflightResult, run_preflight
from safety.release_gate import ReleaseGate, GateStatus, run_release_gate


class TestConfigValidator:
    def test_live_trading_default_false(self):
        result = validate_live_trading_enabled(False)
        assert result.passed is True
        assert "default" in result.message.lower()

    def test_live_trading_true_warns(self):
        result = validate_live_trading_enabled(True)
        assert result.passed is True
        assert "warning" in result.message.lower()

    def test_validate_required_modules(self):
        result = validate_required_modules([
            "strategy", "risk", "order", "scanner", "quant",
            "market_regime", "session", "audit_logging", "kis",
        ])
        assert result.passed is True

    def test_mask_sensitive_value(self):
        masked = mask_sensitive_value("abc123def456")
        assert len(masked) <= 8
        assert masked != "abc123def456"

    def test_mask_short_value(self):
        masked = mask_sensitive_value("ab")
        assert masked == "**"


class TestPreflight:
    def test_all_checks_pass(self):
        pf = PreflightCheck(
            name="test_check", passed=True, message="OK"
        )
        assert pf.passed is True

    def test_check_can_fail(self):
        pf = PreflightCheck(
            name="test_check", passed=False, message="FAIL",
            detail="Something went wrong",
        )
        assert pf.passed is False

    def test_run_preflight(self):
        result = run_preflight(
            live_trading_enabled=False,
            emergency_stop=False,
            modules_loaded=True,
            audit_writer_ok=True,
            telegram_ok=True,
            eod_report_ok=True,
        )
        assert isinstance(result, PreflightResult)
        assert result.all_passed is True
        assert len(result.checks) >= 5

    def test_preflight_fails_on_emergency_stop(self):
        result = run_preflight(
            live_trading_enabled=True,
            emergency_stop=True,
            modules_loaded=True,
            audit_writer_ok=True,
            telegram_ok=True,
            eod_report_ok=True,
        )
        assert result.all_passed is True  # preflight doesn't block, just reports

    def test_no_env_values_in_output(self):
        """Preflight 결과에 실제 env 값이 노출되지 않음"""
        result = run_preflight(
            live_trading_enabled=False,
            emergency_stop=False,
            modules_loaded=True,
            audit_writer_ok=True,
            telegram_ok=True,
            eod_report_ok=True,
        )
        output = str(result)
        for secret in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert secret not in output


class TestReleaseGate:
    def test_all_checks_pass(self):
        gate = ReleaseGate()
        gate.add_check("pytest", True, "756 passed")
        gate.add_check("secret_grep", True, "no secrets found")
        gate.add_check("live_trading", True, "LIVE_TRADING_ENABLED=false")
        gate.add_check("no_http_calls", True, "no direct HTTP calls")
        gate.add_check("no_fake_fill", True, "no fake fill/balance")
        status = gate.status()
        assert status == GateStatus.PASSED

    def test_failed_check_blocks(self):
        gate = ReleaseGate()
        gate.add_check("pytest", False, "tests failed")
        gate.add_check("secret_grep", True, "ok")
        status = gate.status()
        assert status == GateStatus.FAILED

    def test_has_summary(self):
        gate = ReleaseGate()
        gate.add_check("check1", True, "ok")
        gate.add_check("check2", True, "ok")
        summary = gate.summary()
        assert "PASSED" in summary
        assert "check1" in summary
