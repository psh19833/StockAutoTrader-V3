from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache


@dataclass
class _Tick:
    symbol: str
    price: int
    source: str = "REST"
    received_at: datetime | None = None


@dataclass
class _OrderBook:
    symbol: str
    bids: list
    asks: list
    source: str = "REST"
    received_at: datetime | None = None


class FakeRestProvider:
    def __init__(self):
        self.tick_calls: list[str] = []
        self.ob_calls: list[str] = []
        self._tick: dict[str, _Tick | None] = {}
        self._ob: dict[str, _OrderBook | None] = {}

    def set_tick(self, symbol: str, tick: _Tick | None) -> None:
        self._tick[symbol] = tick

    def set_ob(self, symbol: str, ob: _OrderBook | None) -> None:
        self._ob[symbol] = ob

    def get_trade_tick_snapshot(self, symbol: str):
        self.tick_calls.append(symbol)
        return self._tick.get(symbol)

    def get_orderbook_snapshot(self, symbol: str):
        self.ob_calls.append(symbol)
        return self._ob.get(symbol)


def test_cache_hit_does_not_call_rest_provider():
    cache = MarketCache()
    provider = FakeRestProvider()
    router = MarketDataRouter(cache=cache, rest_provider=provider, ws_connected=True)

    cache.put_trade_tick("005930", _Tick(symbol="005930", price=1, received_at=datetime.now(timezone.utc)))
    t = router.get_latest_trade_tick("005930")
    assert t is not None
    assert provider.tick_calls == []


def test_cache_miss_calls_rest_provider_when_configured():
    cache = MarketCache()
    provider = FakeRestProvider()
    provider.set_tick("005930", _Tick(symbol="005930", price=100, received_at=datetime.now(timezone.utc)))

    router = MarketDataRouter(cache=cache, rest_provider=provider, ws_connected=False)
    t = router.get_latest_trade_tick("005930")
    assert t is not None
    assert t.price == 100
    assert provider.tick_calls == ["005930"]


def test_cache_miss_no_provider_returns_none_with_warning():
    router = MarketDataRouter(cache=MarketCache(), rest_provider=None, ws_connected=False)
    t = router.get_latest_trade_tick("005930")
    assert t is None
    st = router.get_status()
    assert any("rest_provider not configured" in w for w in st.get("stale_warnings", []))


def test_stale_cache_triggers_fallback_attempt():
    cache = MarketCache()
    provider = FakeRestProvider()

    old = datetime.now(timezone.utc) - timedelta(seconds=999)
    cache.put_trade_tick("005930", _Tick(symbol="005930", price=1, received_at=old))
    provider.set_tick("005930", _Tick(symbol="005930", price=200, received_at=datetime.now(timezone.utc)))

    router = MarketDataRouter(cache=cache, rest_provider=provider, ws_connected=True, stale_after_seconds=5)
    t = router.get_latest_trade_tick("005930")
    assert t is not None
    assert t.price == 200
    assert provider.tick_calls == ["005930"]


def test_rest_snapshot_without_timestamp_fails_closed():
    provider = FakeRestProvider()
    provider.set_tick("005930", _Tick(symbol="005930", price=400, received_at=None))

    router = MarketDataRouter(cache=MarketCache(), rest_provider=provider, ws_connected=False, stale_after_seconds=5)
    t = router.get_latest_trade_tick("005930")
    assert t is None
    assert provider.tick_calls == ["005930"]
    warnings = router.get_status().get("stale_warnings", [])
    assert any("timestamp missing" in w for w in warnings)
    assert any("rest snapshot stale or invalid" in w for w in warnings)


def test_cache_object_without_timestamp_fails_closed_and_uses_rest_fallback():
    cache = MarketCache()
    provider = FakeRestProvider()

    cache.put_trade_tick("005930", _Tick(symbol="005930", price=1, received_at=None))
    provider.set_tick("005930", _Tick(symbol="005930", price=300, received_at=datetime.now(timezone.utc)))

    router = MarketDataRouter(cache=cache, rest_provider=provider, ws_connected=True, stale_after_seconds=5)
    t = router.get_latest_trade_tick("005930")
    assert t is not None
    assert t.price == 300
    assert provider.tick_calls == ["005930"]
    assert any("timestamp missing" in w for w in router.get_status().get("stale_warnings", []))
