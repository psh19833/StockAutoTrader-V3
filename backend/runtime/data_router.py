"""Market Data Router — unified REST + WebSocket data access layer.

Provides get_latest_* methods that check market_cache first (WS updates),
fall back to REST if needed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from runtime.market_cache import MarketCache
from runtime.data_quality import DataQualityCheck
from runtime.rest_ws_policy import live_source, DataSource
from runtime.rest_market_data_provider import RestMarketDataProvider


class MarketDataRouter:
    """Unified market data access.

    Usage:
        cache = MarketCache()
        router = MarketDataRouter(cache, ws_connected=False)
        tick = router.get_latest_trade_tick("005930")
    """

    def __init__(
        self,
        cache: Optional[MarketCache] = None,
        rest_provider: Optional[RestMarketDataProvider] = None,
        ws_connected: bool = False,
        stale_after_seconds: int = 5,
    ):
        self._cache = cache or MarketCache()
        self._rest_provider = rest_provider
        self._ws_connected = ws_connected
        self._rest_available = rest_provider is not None
        self._stale_warnings: list[str] = []
        self._stale_after_seconds = stale_after_seconds

    @property
    def ws_connected(self) -> bool:
        return self._ws_connected

    @ws_connected.setter
    def ws_connected(self, value: bool) -> None:
        self._ws_connected = value

    @property
    def source(self) -> str:
        return live_source(self._ws_connected).value

    def _is_stale(self, obj: object) -> bool:
        """Best-effort staleness check using received_at or fetched_at."""
        ts = getattr(obj, "received_at", None) or getattr(obj, "fetched_at", None)
        if not isinstance(ts, datetime):
            return False
        now = datetime.now(timezone.utc)
        age = (now - ts).total_seconds()
        return age > float(self._stale_after_seconds)

    # ── Access methods ────────────────────────────────────────────────────

    def get_latest_trade_tick(self, symbol: str):
        tick = self._cache.get_trade_tick(symbol)
        if tick is not None and not self._is_stale(tick):
            return tick

        # cache miss/stale -> REST fallback if available
        if self._rest_provider is None:
            self._stale_warnings.append(
                f"trade_tick unavailable: {symbol} (rest_provider not configured)"
            )
            return None

        try:
            snap = self._rest_provider.get_trade_tick_snapshot(symbol)
        except Exception as e:
            self._stale_warnings.append(
                f"trade_tick rest error: {symbol} ({type(e).__name__})"
            )
            return None

        if snap is None:
            self._stale_warnings.append(f"trade_tick rest returned None: {symbol}")
            return None

        try:
            self._cache.put_trade_tick(symbol, snap)
        except Exception:
            pass
        return snap

    def get_latest_orderbook(self, symbol: str):
        ob = self._cache.get_orderbook(symbol)
        if ob is not None and not self._is_stale(ob):
            return ob

        if self._rest_provider is None:
            self._stale_warnings.append(
                f"orderbook unavailable: {symbol} (rest_provider not configured)"
            )
            return None

        try:
            snap = self._rest_provider.get_orderbook_snapshot(symbol)
        except Exception as e:
            self._stale_warnings.append(
                f"orderbook rest error: {symbol} ({type(e).__name__})"
            )
            return None

        if snap is None:
            self._stale_warnings.append(f"orderbook rest returned None: {symbol}")
            return None

        try:
            self._cache.put_orderbook(symbol, snap)
        except Exception:
            pass
        return snap

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
