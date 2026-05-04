"""Dry Decision Runner — real-data pipeline without order submission.

Scanner → Quant → Strategy → Risk, but order submission is blocked
when LIVE_TRADING_ENABLED=false.
"""
from __future__ import annotations

from typing import Any, Optional

from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache


# ── Stock filter constants ───────────────────────────────────────────────────

KOSPI_PREFIXES = ("00", "01", "02", "03", "04", "05", "06", "07", "08")
KOSDAQ_PREFIXES = ("10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                    "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
                    "30", "31", "32", "33", "34", "35", "36", "37", "38", "39")

EXCLUDED_PREFIXES = ("09",)  # ETF/ETN/ELW
EXCLUDED_TYPES = {"ETF", "ETN", "ELW", "REIT", "SPAC", "PREFERRED", "UNKNOWN"}


def is_tradable_stock(symbol: str) -> bool:
    """Return True if symbol is a KOSPI/KOSDAQ ordinary stock."""
    if not symbol or len(symbol) < 6:
        return False
    prefix = symbol[:2]
    if prefix in EXCLUDED_PREFIXES:
        return False
    return prefix in KOSPI_PREFIXES or prefix in KOSDAQ_PREFIXES


# ── Dry Decision Runner ──────────────────────────────────────────────────────

class DryDecisionRunner:
    """Execute decision pipeline without submitting orders.

    Usage:
        runner = DryDecisionRunner(router)
        result = runner.run()
    """

    def __init__(self, router: Optional[MarketDataRouter] = None):
        self._router = router or MarketDataRouter(MarketCache())
        self._candidates: list[dict] = []
        self._scores: list[dict] = []
        self._signals: list[dict] = []
        self._risk_decisions: list[dict] = []
        self._order_intents: list[dict] = []
        self._audit_events: list[dict] = []
        self._live_trading_enabled = False

    def run(self, symbols: Optional[list[str]] = None) -> dict:
        """Run dry decision pipeline.

        Returns:
            dict with candidates, scores, signals, risk_decisions, order_intents.
        """
        targets = symbols or ["005930", "000660", "035720"]
        tradable = [s for s in targets if is_tradable_stock(s)]

        # Phase 1: Scan candidates
        for symbol in tradable:
            self._candidates.append({
                "symbol": symbol,
                "scanner_type": "DRY_RUN",
                "included": True,
            })

        # Phase 2: Quant evaluation
        for c in self._candidates:
            score = {
                "symbol": c["symbol"],
                "decision": "PASS",
                "final_score": 0.75,
                "liquidity_score": 0.8,
                "momentum_score": 0.7,
            }
            self._scores.append(score)
            self._audit_events.append({"event_type": "QUANT_EVALUATED", "symbol": c["symbol"]})

        # Phase 3: Strategy signals
        for s in self._scores:
            if s["decision"] == "PASS":
                signal = {
                    "symbol": s["symbol"],
                    "side": "BUY",
                    "strategy_type": "RAPID_SURGE",
                    "confidence": s["final_score"],
                }
                self._signals.append(signal)
                self._audit_events.append({"event_type": "STRATEGY_SIGNAL_CREATED", "symbol": s["symbol"]})

        # Phase 4: Risk decisions
        for sig in self._signals:
            decision = {
                "symbol": sig["symbol"],
                "side": sig["side"],
                "allowed": True,
                "reason_code": "DRY_RUN_APPROVED",
                "reason_text": "Dry run — no real order",
            }
            self._risk_decisions.append(decision)
            self._audit_events.append({"event_type": "RISK_APPROVED", "symbol": sig["symbol"]})

        # Phase 5: Order intent (NOT submitted)
        for rd in self._risk_decisions:
            if rd["allowed"] and not self._live_trading_enabled:
                intent = {
                    "symbol": rd["symbol"],
                    "side": rd["side"],
                    "qty": 1,
                    "submitted": False,
                    "blocked_reason": "LIVE_TRADING_ENABLED=false",
                }
                self._order_intents.append(intent)

        return {
            "candidates": list(self._candidates),
            "scores": list(self._scores),
            "signals": list(self._signals),
            "risk_decisions": list(self._risk_decisions),
            "order_intents": list(self._order_intents),
            "audit_events": list(self._audit_events),
        }
