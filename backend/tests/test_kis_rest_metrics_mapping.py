from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache
from runtime.live_scanner import LiveScannerAdapter


class FakeFacade:
    def __init__(self, price: dict, orderbook: dict):
        self._price = price
        self._ob = orderbook

    def get_current_price(self, symbol: str) -> dict:
        return dict(self._price)

    def get_orderbook(self, symbol: str) -> dict:
        return dict(self._ob)

    def get_execution_strength(self, symbol: str) -> dict:
        # Should not be required for accumulated volume/value mapping
        return {"data_available": False}


def test_rest_tick_prefers_accumulated_volume_and_value_for_scanner_metrics() -> None:
    # Simulate KIS inquire-price response fields already parsed by MarketDataApi
    price = {
        "data_available": True,
        "current_price": 70000,
        "change_price": 1000,
        "accumulated_volume": 2_000_000,
        "accumulated_trading_value": 1_200_000_000_000,
        "change_rate": 1.4,
    }
    ob = {"data_available": True, "ask_price": 70100, "bid_price": 70000}

    from typing import Any, cast
    from runtime.kis_rest_market_data_provider import KisRestMarketDataProvider

    provider = KisRestMarketDataProvider(cast(Any, FakeFacade(price, ob)))
    router = MarketDataRouter(MarketCache(), rest_provider=provider)
    adapter = LiveScannerAdapter(router)

    row = adapter._build_stock_metrics("005930")
    assert row is not None

    assert row["current_price"] == 70000
    # Volume should come from accumulated_volume (not 1)
    assert row["volume"] == 2_000_000
    # Trading value should come from accumulated_trading_value (not price*volume fallback)
    assert row["trading_value"] == 1_200_000_000_000


def test_rest_tick_does_not_use_orderbook_qty_as_volume() -> None:
    price = {
        "data_available": True,
        "current_price": 50000,
        "change_price": 0,
        "accumulated_volume": 0,  # missing
        "accumulated_trading_value": 0,  # missing
        "change_rate": 0.0,
    }
    ob = {"data_available": True, "ask_price": 50100, "bid_price": 50000, "ask_qty": 1, "bid_qty": 1}

    from typing import Any, cast
    from runtime.kis_rest_market_data_provider import KisRestMarketDataProvider

    provider = KisRestMarketDataProvider(cast(Any, FakeFacade(price, ob)))
    router = MarketDataRouter(MarketCache(), rest_provider=provider)
    adapter = LiveScannerAdapter(router)

    row = adapter._build_stock_metrics("005930")
    assert row is not None

    # With no accumulated volume/trading value provided, we must NOT use orderbook quantities.
    # Volume should remain 0 (not forced to 1).
    assert row["volume"] == 0
    # Trading value may fall back to price*max(volume,1) => price, but must not come from orderbook.
    # We only assert it's a sane integer and does not imply orderbook-qty usage.
    assert isinstance(row["trading_value"], int)
    assert row["trading_value"] >= 0
