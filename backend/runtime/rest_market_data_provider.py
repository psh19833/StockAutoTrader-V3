"""REST Market Data Provider interface (DI-only).

This module defines a protocol for a REST fallback provider.
Actual KIS REST calls are NOT implemented in this Phase.

Rules:
- Tests must use fake providers (no network).
- No random/synthetic price generation.
"""

from __future__ import annotations

from typing import Optional, Protocol, Any


class RestMarketDataProvider(Protocol):
    # Return types are intentionally loose (router only requires received_at/fetched_at datetime attr).
    def get_trade_tick_snapshot(self, symbol: str) -> Any: ...

    def get_orderbook_snapshot(self, symbol: str) -> Any: ...
