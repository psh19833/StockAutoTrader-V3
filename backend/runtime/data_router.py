"""Market Data Router — unified REST + WebSocket data access layer.

Provides get_latest_* methods that check market_cache first (WS updates),
fall back to REST if needed.
"""
from __future__ import annotations

from typing import Optional

from runtime.market_cache import MarketCache
from runtime.data_quality import DataQualityCheck
from runtime.rest_ws_policy import live_source, DataSource


class MarketDataRouter:
    """Unified market data access.

    Usage:
        cache = MarketCache()
        router = MarketDataRouter(cache, ws_connected=False)
        tick = router.get_latest_trade_tick("005930")
    """

    def __init__(self, cache: Optional[MarketCache] = None, ws_connected: bool = False):
        self._cache = cache or MarketCache()
        self._ws_connected = ws_connected
        self._rest_available = True
        self._stale_warnings: list[str] = []

    @property
    def ws_connected(self) -> bool:
        return self._ws_connected

    @ws_connected.setter
    def ws_connected(self, value: bool) -> None:
        self._ws_connected = value

    @property
    def source(self) -> str:
        return live_source(self._ws_connected).value

    # ── Access methods ────────────────────────────────────────────────────

    def get_latest_trade_tick(self, symbol: str):
        return self._cache.get_trade_tick(symbol)

    def get_latest_orderbook(self, symbol: str):
        return self._cache.get_orderbook(symbol)

    def get_latest_market_status(self):
        return self._cache.get_market_status()

    def get_latest_expected_execution(self, symbol: str):
        return self._cache.get_expected_execution(symbol)

    # ── Update from WS ────────────────────────────────────────────────────

    def on_ws_trade_tick(self, tick) -> None:
        self._cache.put_trade_tick(tick.symbol, tick)

    def on_ws_orderbook(self, ob) -> None:
        self._cache.put_orderbook(ob.symbol, ob)

    def on_ws_market_status(self, status) -> None:
        self._cache.put_market_status(status)

    def on_ws_expected_execution(self, ee) -> None:
        self._cache.put_expected_execution(ee.symbol, ee)

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "ws_connected": self._ws_connected,
            "rest_available": self._rest_available,
            "stale_warnings": list(self._stale_warnings),
            "source": self.source,
        }

    def check_data_quality(self) -> None:
        self._stale_warnings = DataQualityCheck.check_ws_disconnect_risk(
            ws_connected=self._ws_connected,
            last_ws_message_at=getattr(self._cache.get_market_status(), "received_at", None)
            if self._cache.get_market_status() else None,
        )
