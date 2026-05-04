"""Market data cache — symbol-level latest quote/orderbook/tick/status cache.

Stores latest data from REST (initial) and WebSocket (real-time updates).
Each entry tracks source (REST/WS) and fetched_at/received_at timestamps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from kis.ws_models import (
    RealtimeTradeTick,
    RealtimeOrderBook,
    RealtimeMarketStatus,
    RealtimeExpectedExecution,
)


class MarketCache:
    """Thread-safe-ish market data cache (per-symbol)."""

    def __init__(self):
        self._trade_ticks: dict[str, RealtimeTradeTick] = {}
        self._orderbooks: dict[str, RealtimeOrderBook] = {}
        self._market_status: Optional[RealtimeMarketStatus] = None
        self._expected_executions: dict[str, RealtimeExpectedExecution] = {}
        self._sources: dict[str, str] = {}

    # ── Trade ticks ───────────────────────────────────────────────────────

    def put_trade_tick(self, symbol: str, tick: RealtimeTradeTick) -> None:
        self._trade_ticks[symbol] = tick
        self._sources[f"{symbol}:tick"] = tick.source

    def get_trade_tick(self, symbol: str) -> Optional[RealtimeTradeTick]:
        return self._trade_ticks.get(symbol)

    # ── Order books ───────────────────────────────────────────────────────

    def put_orderbook(self, symbol: str, ob: RealtimeOrderBook) -> None:
        self._orderbooks[symbol] = ob
        self._sources[f"{symbol}:orderbook"] = ob.source

    def get_orderbook(self, symbol: str) -> Optional[RealtimeOrderBook]:
        return self._orderbooks.get(symbol)

    # ── Market status ─────────────────────────────────────────────────────

    def put_market_status(self, status: RealtimeMarketStatus) -> None:
        self._market_status = status

    def get_market_status(self) -> Optional[RealtimeMarketStatus]:
        return self._market_status

    # ── Expected executions ───────────────────────────────────────────────

    def put_expected_execution(self, symbol: str, ee: RealtimeExpectedExecution) -> None:
        self._expected_executions[symbol] = ee

    def get_expected_execution(self, symbol: str) -> Optional[RealtimeExpectedExecution]:
        return self._expected_executions.get(symbol)

    # ── Source tracking ───────────────────────────────────────────────────

    def get_source(self, key: str) -> str:
        return self._sources.get(key, "unknown")

    def clear(self) -> None:
        self._trade_ticks.clear()
        self._orderbooks.clear()
        self._market_status = None
        self._expected_executions.clear()
        self._sources.clear()
