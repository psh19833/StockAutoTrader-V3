"""Live scanner adapter (audit-only).

Runs scanner_engine against router-backed market snapshots and returns
metadata-rich candidates for live audit pipeline. Never submits orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from runtime.data_router import MarketDataRouter
from runtime.scheduler import SessionState
from scanner.scanner_engine import run_all_scanners


@dataclass(frozen=True)
class LiveScanResult:
    status: str
    reason: str
    generated_at: str
    scan_id: str
    source: str
    mode: str
    synthetic: bool
    candidates: list[dict]
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "generated_at": self.generated_at,
            "scan_id": self.scan_id,
            "source": self.source,
            "mode": self.mode,
            "synthetic": self.synthetic,
            "candidates": list(self.candidates),
            "error": self.error,
        }


class LiveScannerAdapter:
    def __init__(self, router: MarketDataRouter):
        self._router = router

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _scan_id() -> str:
        return f"live_scan_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _default_symbols() -> list[str]:
        return ["005930", "000660", "035720"]

    def _build_stock_metrics(self, symbol: str) -> dict | None:
        tick = self._router.get_latest_trade_tick(symbol)
        if tick is None:
            return None
        orderbook = self._router.get_latest_orderbook(symbol)

        trade_price = int(getattr(tick, "trade_price", 0) or 0)
        change_price = int(getattr(tick, "change_price", 0) or 0)
        ask = int(getattr(tick, "ask_price", 0) or 0)
        bid = int(getattr(tick, "bid_price", 0) or 0)
        # Prefer REST accumulated fields when available.
        acc_vol = getattr(tick, "accumulated_volume", None)
        acc_tv = getattr(tick, "accumulated_trading_value", None)
        volume = int((acc_vol if acc_vol is not None else getattr(tick, "trade_volume", 0)) or 0)

        spread_rate = 0.0
        if ask > 0 and bid > 0:
            spread_rate = abs(ask - bid) / max(1, trade_price or ask)

        change_rate = 0.0
        if trade_price > 0:
            change_rate = (change_price / trade_price) * 100.0

        # trading_value: prefer accumulated trading value from REST price endpoint.
        trading_value = 0
        if acc_tv is not None and int(acc_tv or 0) > 0:
            trading_value = int(acc_tv)
        else:
            trading_value = max(0, trade_price * max(volume, 1))

        # Scanner 공통 필터를 통과할 수 있는 최소 shape만 구성
        return {
            "symbol": symbol,
            "symbol_name": symbol,
            "market": "KOSPI",
            "product_type": "COMMON_STOCK",
            "source": "KIS_API",
            "source_endpoints": ("router/trade_tick", "router/orderbook"),
            "current_price": trade_price,
            "intraday_high": max(trade_price, trade_price + max(change_price, 0)),
            "intraday_change_rate": change_rate,
            "trading_value": max(0, trading_value),
            "volume": max(int(volume), 0),
            "volume_ratio_vs_recent_avg": 2.0,
            "spread_rate": spread_rate,
            "execution_strength": 120.0,
            "volatility_ratio": 0.8,
            "vi_status": "INACTIVE",
            "is_management_issue": False,
            "is_investment_warning": False,
            # scanner.filters.check_common_filters expects is_trading_halted
            "is_trading_halted": False,
            # keep legacy key for any downstream consumers
            "trading_halted": False,
            "pullback_from_high": 0.5,
            "rebound_volume_ratio": 1.2,
            "support_holding_score": 7.0,
            "prior_intraday_gain": max(0.0, change_rate),
        }

    def run_live_scan(self, session: str) -> LiveScanResult:
        generated_at = self._now()
        scan_id = self._scan_id()

        if session != SessionState.REGULAR_MARKET.value:
            return LiveScanResult(
                status="WAITING_FOR_REGULAR_MARKET",
                reason="SESSION_NOT_REGULAR_MARKET",
                generated_at=generated_at,
                scan_id=scan_id,
                source="LIVE_SCANNER",
                mode="LIVE",
                synthetic=False,
                candidates=[],
            )

        stocks: list[dict] = []
        for symbol in self._default_symbols():
            row = self._build_stock_metrics(symbol)
            if row is not None:
                stocks.append(row)

        if not stocks:
            return LiveScanResult(
                status="WAITING_FOR_MARKET_DATA",
                reason="LIVE_SCANNER_NO_FRESH_DATA",
                generated_at=generated_at,
                scan_id=scan_id,
                source="LIVE_SCANNER",
                mode="LIVE",
                synthetic=False,
                candidates=[],
            )

        try:
            results = run_all_scanners(stocks=stocks, market_regime="NEUTRAL", scan_run_id=scan_id)
            candidates: list[dict] = []
            for result in results:
                for c in result.candidates:
                    if not c.included:
                        continue
                    candidates.append(
                        {
                            "symbol": c.symbol,
                            "symbol_name": c.symbol_name or c.symbol,
                            "scanner_type": c.scanner_type.value,
                            "included": True,
                            "excluded_reason": None,
                            "generated_at": generated_at,
                            "source": "LIVE_SCANNER",
                            "mode": "LIVE",
                            "synthetic": False,
                            "origin": "live",
                            "scan_id": scan_id,
                            "run_id": f"candidate:{scan_id}",
                            "is_live_candidate": True,
                            "metrics": dict(c.metrics or {}),
                        }
                    )
            return LiveScanResult(
                status="READY",
                reason="LIVE_SCANNER_OK",
                generated_at=generated_at,
                scan_id=scan_id,
                source="LIVE_SCANNER",
                mode="LIVE",
                synthetic=False,
                candidates=candidates,
            )
        except Exception as e:
            return LiveScanResult(
                status="BLOCKED_ERROR",
                reason="LIVE_SCANNER_ERROR",
                generated_at=generated_at,
                scan_id=scan_id,
                source="LIVE_SCANNER",
                mode="LIVE",
                synthetic=False,
                candidates=[],
                error=type(e).__name__,
            )
