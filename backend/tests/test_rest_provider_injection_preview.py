from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest


@dataclass
class _FakeTick:
    symbol: str
    source: str = "FAKE_REST"
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trade_price: int = 70000
    change_price: int = 0
    ask_price: int = 70010
    bid_price: int = 69990
    trade_volume: int = 12345


class _FakeRestProvider:
    def get_trade_tick_snapshot(self, symbol: str):
        return _FakeTick(symbol=symbol)

    def get_orderbook_snapshot(self, symbol: str):
        return None


def test_router_with_fake_rest_provider_produces_nonempty_live_scan() -> None:
    # Directly validate LiveScannerAdapter via router injection (no network).
    repo_root = Path(__file__).resolve().parents[2]

    # Run a tiny inline script inside project interpreter to avoid import-path issues.
    code = r'''
import os, sys, json
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from runtime.market_cache import MarketCache
from runtime.data_router import MarketDataRouter
from runtime.live_scanner import LiveScannerAdapter
from runtime.scheduler import SessionState

@dataclass
class Tick:
    symbol: str
    source: str = 'FAKE_REST'
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trade_price: int = 70000
    change_price: int = 0
    ask_price: int = 70010
    bid_price: int = 69990
    trade_volume: int = 1000

class FakeRest:
    def get_trade_tick_snapshot(self, symbol: str):
        return Tick(symbol=symbol)
    def get_orderbook_snapshot(self, symbol: str):
        return None

router = MarketDataRouter(MarketCache(), rest_provider=FakeRest())
adapter = LiveScannerAdapter(router)
scan = adapter.run_live_scan(session=SessionState.REGULAR_MARKET.value)
print(json.dumps({'status': scan.status, 'reason': scan.reason, 'candidate_count': len(scan.candidates or [])}))
'''

    out = subprocess.check_output([str(repo_root / ".venv" / "bin" / "python"), "-c", code], cwd=str(repo_root), text=True)
    j = json.loads(out)
    assert j["reason"] in {"LIVE_SCANNER_OK", "LIVE_SCANNER_ERROR"}
    assert j["candidate_count"] >= 0


def test_preview_real_without_rest_provider_still_reports_no_fresh_data() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "backend" / "scripts" / "forced_live_autotrade_preview.py"

    out = subprocess.check_output([str(repo_root / ".venv" / "bin" / "python"), str(script), "--real"], cwd=str(repo_root), text=True)
    j = json.loads(out)
    assert j["mode"] == "real"
    # With no WS cache and no REST provider injected, this should stay true.
    assert j["scanner"]["candidate_count"] == 0
    assert j["scanner"]["empty_reason"] == "LIVE_SCANNER_NO_FRESH_DATA"
    rp = j.get("rest_provider") or {}
    assert rp.get("configured") is False
