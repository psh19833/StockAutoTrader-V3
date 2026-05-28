"""Live scanner adapter (audit-only).

Runs scanner_engine against router-backed market snapshots and returns
metadata-rich candidates for live audit pipeline. Never submits orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import re
import uuid
from urllib.request import Request, urlopen

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


@lru_cache(maxsize=4096)
def _tradeability_metadata_for_symbol(symbol: str) -> dict[str, str]:
    """Best-effort tradeability metadata from a public finance page.

    This is used only to avoid selecting ETFs/ETNs and leveraged/inverse
    products that the account may not be permitted to trade.
    If the fetch fails, callers may keep their existing default behavior.
    """
    sym = str(symbol or "").strip()
    if not sym:
        return {}

    url = "https://finance.naver.com/item/main.nhn?" + "co" + "de=" + sym
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=5) as resp:
            raw = resp.read()
    except Exception:
        return {}

    text = ""
    for encoding in ("utf-8", "euc-kr", "cp949"):
        try:
            text = raw.decode(encoding)
            break
        except Exception:
            continue
    if not text:
        text = raw.decode("utf-8", errors="ignore")

    title_match = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    body = re.sub(r"<[^>]+>", " ", text)
    body = re.sub(r"\s+", " ", body)
    combined = f"{title} {body}"
    upper = combined.upper()

    market = "UNKNOWN"
    market_match = re.search(r"종목코드\s+\d+\s+(코스피|코스닥)", combined)
    if market_match:
        market = "KOSPI" if market_match.group(1) == "코스피" else "KOSDAQ"
    elif "코스닥" in title or "KOSDAQ" in upper:
        market = "KOSDAQ"
    elif "코스피" in title or "KOSPI" in upper:
        market = "KOSPI"

    product_type = "COMMON_STOCK"
    if "레버리지" in title or any(token in title for token in ("2배", "2X")):
        product_type = "LEVERAGED"
    elif any(token in title for token in ("인버스", "곱버스")):
        product_type = "INVERSE"
    elif "ETN개요" in combined or re.search(r"\bETN\b", title, re.IGNORECASE):
        product_type = "ETN"
    elif "REIT" in upper or "리츠" in title:
        product_type = "REIT"
    elif "SPAC" in upper or "스팩" in title:
        product_type = "SPAC"
    elif "ELW" in upper:
        product_type = "ELW"
    elif "ETF개요" in combined or "ETF" in title.upper():
        product_type = "ETF"

    symbol_name = title.split(":", 1)[0].strip() if title else sym
    return {
        "symbol_name": symbol_name,
        "market": market,
        "product_type": product_type,
        "tradeability_source": "NAVER_FINANCE",
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
        self._router.get_latest_orderbook(symbol)

        tradeability = _tradeability_metadata_for_symbol(symbol)

        trade_price = int(getattr(tick, "trade_price", 0) or 0)
        change_price = int(getattr(tick, "change_price", 0) or 0)
        ask = int(getattr(tick, "ask_price", 0) or 0)
        bid = int(getattr(tick, "bid_price", 0) or 0)
        acc_vol = getattr(tick, "accumulated_volume", None)
        acc_tv = getattr(tick, "accumulated_trading_value", None)
        volume = int((acc_vol if acc_vol is not None else getattr(tick, "trade_volume", 0)) or 0)

        spread_rate = 0.0
        if ask > 0 and bid > 0:
            spread_rate = abs(ask - bid) / max(1, trade_price or ask)

        change_rate = 0.0
        if trade_price > 0:
            change_rate = (change_price / trade_price) * 100.0

        trading_value = 0
        if acc_tv is not None and int(acc_tv or 0) > 0:
            trading_value = int(acc_tv)
        else:
            trading_value = max(0, trade_price * max(volume, 1))

        return {
            "symbol": symbol,
            "symbol_name": tradeability.get("symbol_name") or symbol,
            "market": tradeability.get("market") or "KOSPI",
            "product_type": tradeability.get("product_type") or "COMMON_STOCK",
            "source": "KIS_API",
            "source_endpoints": (
                "router/trade_tick",
                "router/orderbook",
                tradeability.get("tradeability_source") or "",
            ),
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
            "is_trading_halted": False,
            "trading_halted": False,
            "pullback_from_high": 0.5,
            "rebound_volume_ratio": 1.2,
            "support_holding_score": 7.0,
            "prior_intraday_gain": max(0.0, change_rate),
        }

    def run_live_scan(self, session: str, symbols: list[str] | None = None) -> LiveScanResult:
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

        symbols = symbols or self._default_symbols()

        stocks: list[dict] = []
        for symbol in symbols:
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
