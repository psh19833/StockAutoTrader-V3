from __future__ import annotations

import asyncio
import time

import main


def _run(coro):
    return asyncio.run(coro)


def test_runtime_tick_updates_dashboard_read_models():
    result = _run(main.runtime_tick(mode="dry-run", session="REGULAR_MARKET"))
    assert result.get("mode") == "dry-run"
    dry = result.get("dry_run", {})
    counts = dry.get("counts", {})
    assert counts.get("candidates", 0) >= 1
    assert counts.get("scores", 0) >= 1
    assert counts.get("signals", 0) >= 1


def test_runtime_tick_rejects_live_mode_when_preconditions_fail():
    result = _run(main.runtime_tick(mode="live", session="REGULAR_MARKET"))
    assert result.get("mode") == "live"
    assert result.get("status") == "RUNTIME_LIVE_MODE_BLOCKED"
    assert result.get("reason") == "LIVE_START_PRECONDITION_FAILED"
    assert result.get("executed") is False
    assert isinstance(result.get("block_reasons"), list)


def test_runtime_start_rejects_live_mode_when_preconditions_fail():
    started = _run(main.runtime_start(mode="live", session="REGULAR_MARKET", interval_sec=1))
    assert started.get("started") is False
    assert started.get("reason") == "LIVE_START_PRECONDITION_FAILED"
    status = started.get("status", {})
    assert status.get("running") is False


def test_runtime_dry_run_still_works():
    result = _run(main.runtime_tick(mode="dry-run", session="REGULAR_MARKET"))
    assert result.get("mode") == "dry-run"
    dry = result.get("dry_run", {})
    assert isinstance(dry.get("counts"), dict)


def test_runtime_start_status_stop_cycle():
    started = _run(main.runtime_start(mode="dry-run", session="REGULAR_MARKET", interval_sec=1))
    assert started.get("started") is True or started.get("reason") == "already_running"

    time.sleep(1.2)

    status = _run(main.runtime_status())
    assert isinstance(status, dict)
    assert status.get("mode") == "dry-run"
    assert status.get("session") == "REGULAR_MARKET"
    assert int(status.get("tick_count", 0)) >= 1

    stopped = _run(main.runtime_stop())
    assert stopped.get("stopped") is True
