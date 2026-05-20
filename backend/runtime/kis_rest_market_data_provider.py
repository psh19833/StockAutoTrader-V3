"""KIS REST-backed market data provider (GET-only).

Implements runtime.rest_market_data_provider.RestMarketDataProvider protocol.

Safety:
- GET-only quotation endpoints via KisQueryFacade / MarketDataApi.
- No order endpoints.
- No submit_cash_order.

This provider is intended for read-only scanner inputs when WS cache is empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from kis.query_facade import KisQueryFacade
from kis.ws_models import RealtimeOrderBook


@dataclass
class RestTradeTickSnapshot:
    """REST snapshot shaped like a trade tick, but can carry extra fields.

    MarketDataRouter requires a timestamp attribute: received_at/fetched_at.
    LiveScannerAdapter uses trade_price/trade_volume/change_price/ask_price/bid_price.
    """

    source: str
    symbol: str
    received_at: datetime
    trade_price: int
    trade_volume: int
    change_price: int
    ask_price: int
    bid_price: int
    parsed_ok: bool = True

    # Extra fields for scanner metrics mapping
    accumulated_volume: int = 0
    accumulated_trading_value: int = 0


@dataclass
class KisRestProviderStatus:
    configured: bool
    provider_type: str
    last_error_type: Optional[str] = None


class KisRestMarketDataProvider:
    """GET-only REST provider returning snapshot objects with fetched_at."""

    def __init__(self, facade: KisQueryFacade):
        self._facade = facade
        self._last_error_type: Optional[str] = None

    @property
    def status(self) -> KisRestProviderStatus:
        return KisRestProviderStatus(
            configured=True,
            provider_type=type(self).__name__,
            last_error_type=self._last_error_type,
        )

    def get_trade_tick_snapshot(self, symbol: str):
        # Compose a tick-like snapshot from price/orderbook.
        now = datetime.now(timezone.utc)

        price = self._facade.get_current_price(symbol)
        if not price.get("data_available"):
            self._last_error_type = str(price.get("error_type") or "DataUnavailable")
            return None

        ob = self._facade.get_orderbook(symbol)

        trade_price = int(price.get("current_price") or 0)
        change_price = int(price.get("change_price") or 0)
        if change_price == 0:
            change_rate = float(price.get("change_rate") or 0.0)
            change_price = int(trade_price * (change_rate / 100.0)) if trade_price > 0 else 0

        acc_volume = int(price.get("accumulated_volume") or 0)
        acc_trading_value = int(price.get("accumulated_trading_value") or 0)

        ask = int(ob.get("ask_price") or 0) if ob.get("data_available") else 0
        bid = int(ob.get("bid_price") or 0) if ob.get("data_available") else 0

        # IMPORTANT: never use orderbook quantities as "volume".
        # Use accumulated volume from inquire-price.
        volume = acc_volume

        tick = RestTradeTickSnapshot(
            source="KIS_API_REST",
            symbol=symbol,
            received_at=now,
            trade_price=trade_price,
            trade_volume=volume,
            change_price=change_price,
            ask_price=ask,
            bid_price=bid,
            parsed_ok=True,
            accumulated_volume=acc_volume,
            accumulated_trading_value=acc_trading_value,
        )
        return tick

    def get_orderbook_snapshot(self, symbol: str):
        now = datetime.now(timezone.utc)
        ob = self._facade.get_orderbook(symbol)
        if not ob.get("data_available"):
            self._last_error_type = str(ob.get("error_type") or "DataUnavailable")
            return None

        # Minimal 1-level orderbook.
        ask = int(ob.get("ask_price") or 0)
        bid = int(ob.get("bid_price") or 0)
        book = RealtimeOrderBook(
            source="KIS_API_REST",
            symbol=symbol,
            received_at=now,
            ask_prices=[ask] if ask > 0 else [],
            bid_prices=[bid] if bid > 0 else [],
            parsed_ok=True,
        )
        return book
