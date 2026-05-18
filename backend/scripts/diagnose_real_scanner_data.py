"""SAT3 real scanner data-router diagnostic (read-only).

Purpose:
- Explain why LiveScannerAdapter returns candidate_count=0 during regular market.
- Inspect MarketDataRouter / MarketCache state without starting live trading.
- No order submission, no runtime tick loop.

Output: JSON to stdout.

Safety:
- Does NOT call submit_cash_order / transport.post_json
- Does NOT call live auto trading start / runtime tick
- Only constructs in-memory MarketCache + MarketDataRouter (no rest_provider by default)
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone
from typing import Any

# Ensure `backend/` is on sys.path when running as a script.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from runtime.market_cache import MarketCache
from runtime.data_router import MarketDataRouter
from runtime.live_scanner import LiveScannerAdapter
from runtime.scheduler import SessionState


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_cache_symbols(cache: MarketCache) -> dict[str, int]:
    # MarketCache stores dicts; we only read counts (read-only).
    return {
        "trade_tick_symbol_count": len(getattr(cache, "_trade_ticks", {}) or {}),
        "orderbook_symbol_count": len(getattr(cache, "_orderbooks", {}) or {}),
        "expected_execution_symbol_count": len(getattr(cache, "_expected_executions", {}) or {}),
        "has_market_status": 1 if getattr(cache, "_market_status", None) is not None else 0,
    }


def _peek_obj_ts(obj: Any) -> str | None:
    ts = getattr(obj, "received_at", None) or getattr(obj, "fetched_at", None)
    if isinstance(ts, datetime):
        return ts.isoformat()
    return None


def _router_symbol_probe(router: MarketDataRouter, symbol: str) -> dict[str, Any]:
    tick = router.get_latest_trade_tick(symbol)
    ob = router.get_latest_orderbook(symbol)
    return {
        "symbol": symbol,
        "tick_present": tick is not None,
        "tick_ts": _peek_obj_ts(tick) if tick else None,
        "orderbook_present": ob is not None,
        "orderbook_ts": _peek_obj_ts(ob) if ob else None,
    }


def main(argv: list[str]) -> int:
    cache = MarketCache()

    # Optional REST provider injection (GET-only) for diagnosis
    rest_provider = None
    rest_provider_meta = {"configured": False, "reason": "disabled"}
    if os.getenv("SAT3_DIAG_USE_REAL_REST", "").strip().lower() in {"1", "true", "yes"}:
        from runtime.rest_provider_factory import maybe_create_kis_rest_provider

        rest_provider, rest_provider_meta = maybe_create_kis_rest_provider()

    router = MarketDataRouter(cache, rest_provider=rest_provider)
    adapter = LiveScannerAdapter(router)

    # Probe the default symbols used by LiveScannerAdapter
    symbols = ["005930", "000660", "035720"]
    probes = [_router_symbol_probe(router, s) for s in symbols]

    scan = adapter.run_live_scan(session=SessionState.REGULAR_MARKET.value)

    out: dict[str, Any] = {
        "mode": "real_scanner_data_diag",
        "generated_at": _utc_now(),
        "actual_order_submitted": False,
        "live_start_called": False,
        "runtime_tick_called": False,
        "router": {
            "ws_connected": router.ws_connected,
            "rest_available": rest_provider is not None,
            "rest_provider": rest_provider_meta,
            "stale_after_seconds": getattr(router, "_stale_after_seconds", None),
            "status": router.get_status(),
        },
        "cache": _count_cache_symbols(cache),
        "symbol_probes": probes,
        "live_scan": {
            "status": scan.status,
            "reason": scan.reason,
            "scan_id": scan.scan_id,
            "candidate_count": len(scan.candidates or []),
        },
        "direct_empty_condition": "stocks list empty when _build_stock_metrics returns None for all default symbols",
        "next_required_action": None,
    }

    if scan.reason == "LIVE_SCANNER_NO_FRESH_DATA":
        # Root cause inference based on code: no tick available from router.
        # Under current router config, this typically means:
        # - WS ingestion not connected (cache empty)
        # - REST fallback not configured (rest_provider None)
        out["next_required_action"] = "connect_readonly_market_data_ingestion_or_configure_rest_provider_for_router"

    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
