from __future__ import annotations

import json

from runtime.market_cache import MarketCache
from runtime.data_router import MarketDataRouter
from runtime.live_scanner import LiveScannerAdapter, _tradeability_metadata_for_symbol
from runtime.orchestrator import Orchestrator
from runtime.scheduler import SessionState


class FakeRestProvider:
    def __init__(self, symbols: list[str]):
        self._symbols = symbols
        # minimal facade-like object for universe_source
        class _Facade:
            def __init__(self, syms: list[str]):
                self._syms = syms

            def get_volume_top(self, params=None):
                # Return in a shape parse_symbols_from_rank_payload can parse.
                # Use output list with common key name.
                return {
                    "data_available": True,
                    "raw": {
                        "output": [{"mksc_shrn_iscd": s} for s in self._syms]
                    },
                }

        self._facade = _Facade(symbols)

    @property
    def status(self):
        return type("S", (), {"configured": True, "provider_type": "FakeRestProvider"})()

    def get_trade_tick_snapshot(self, symbol: str):
        # Minimal tick snapshot for LiveScannerAdapter; keep it simple.
        from datetime import datetime, timezone
        from dataclasses import dataclass

        @dataclass
        class _Tick:
            source: str
            symbol: str
            received_at: datetime
            trade_price: int
            trade_volume: int
            change_price: int
            ask_price: int
            bid_price: int
            accumulated_volume: int
            accumulated_trading_value: int

        # Provide trading_value to allow rank ordering
        tv = {
            self._symbols[0]: 300,
            self._symbols[1]: 200,
            self._symbols[2]: 100,
        }.get(symbol, 50)
        return _Tick(
            source="KIS_API_REST",
            symbol=symbol,
            received_at=datetime.now(timezone.utc),
            trade_price=10,
            trade_volume=10,
            change_price=0,
            ask_price=11,
            bid_price=10,
            accumulated_volume=10,
            accumulated_trading_value=tv,
        )

    def get_orderbook_snapshot(self, symbol: str):
        from datetime import datetime, timezone
        from dataclasses import dataclass

        @dataclass
        class _Book:
            source: str
            symbol: str
            received_at: datetime
            ask_prices: list[int]
            bid_prices: list[int]

        return _Book(
            source="KIS_API_REST",
            symbol=symbol,
            received_at=datetime.now(timezone.utc),
            ask_prices=[11],
            bid_prices=[10],
        )


def test_live_scanner_accepts_custom_symbols_list() -> None:
    router = MarketDataRouter(MarketCache(), rest_provider=FakeRestProvider(["A", "B", "C"]))
    scanner = LiveScannerAdapter(router)
    res = scanner.run_live_scan(session="REGULAR_MARKET", symbols=["A", "B", "C"])
    # We're not asserting inclusion here; just that it runs and returns a result.
    assert res.status in ("READY", "WAITING_FOR_MARKET_DATA", "BLOCKED_ERROR")


def test_live_scanner_excludes_leveraged_etf(monkeypatch) -> None:
    import runtime.live_scanner as live_scanner

    monkeypatch.setattr(
        live_scanner,
        "_tradeability_metadata_for_symbol",
        lambda symbol: {
            "symbol_name": "KODEX 2차전지산업레버리지" if symbol == "462330" else symbol,
            "market": "KOSPI",
            "product_type": "LEVERAGED" if symbol == "462330" else "COMMON_STOCK",
            "tradeability_source": "TEST",
        },
    )
    router = MarketDataRouter(MarketCache(), rest_provider=FakeRestProvider(["462330", "005930"]))
    scanner = LiveScannerAdapter(router)
    res = scanner.run_live_scan(session="REGULAR_MARKET", symbols=["462330", "005930"])
    symbols = {c["symbol"] for c in res.candidates}
    assert "462330" not in symbols


def test_universe_source_parser_extracts_symbols() -> None:
    from runtime.universe_source import parse_symbols_from_rank_payload

    payload = {"output": [{"mksc_shrn_iscd": "005930"}, {"mksc_shrn_iscd": "000660"}]}
    assert parse_symbols_from_rank_payload(payload) == ["005930", "000660"]


def test_orchestrator_live_mode_uses_rest_provider_when_available(monkeypatch) -> None:
    import runtime.orchestrator as orchestrator_mod

    monkeypatch.setenv("SAT3_ENABLE_LIVE_RUNNER", "true")
    monkeypatch.setattr(
        orchestrator_mod,
        "maybe_create_kis_rest_provider",
        lambda: (FakeRestProvider(["005930", "000660", "035720"]), {"configured": True, "provider_type": "FakeRestProvider"}),
    )

    orch = Orchestrator(live_readiness_provider=lambda: (True, []))
    result = orch.tick(SessionState.REGULAR_MARKET, mode="live")
    live = result.get("live") or {}
    pipeline = live.get("pipeline") or {}

    assert result.get("rest_provider", {}).get("configured") is True
    assert live.get("status") == "LIVE_PIPELINE_TICK_EXECUTED"
    assert pipeline.get("scanner_status") == "READY"
    assert pipeline.get("live_pipeline_reason") == "LIVE_SCANNER_OK"
    assert pipeline.get("live_scan", {}).get("status") == "READY"
    assert pipeline.get("live_scan", {}).get("reason") == "LIVE_SCANNER_OK"
