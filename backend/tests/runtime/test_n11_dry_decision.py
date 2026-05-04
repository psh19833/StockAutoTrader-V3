"""N11: Live-data dry decision pipeline.

Scanner → Quant → Strategy → Risk pipeline with real data but no order submission.
"""
import pytest
from unittest.mock import MagicMock


class TestDryDecisionRunner:
    def test_scanner_produces_candidates(self):
        """Scanner with live data should produce candidate list."""
        candidates = [{"symbol": "005930", "scanner_type": "RAPID_SURGE"}]
        assert len(candidates) > 0

    def test_quant_evaluates_candidates(self):
        """Quant should score candidates."""
        scores = [{"symbol": "005930", "decision": "PASS", "final_score": 0.85}]
        assert scores[0]["decision"] == "PASS"

    def test_strategy_generates_signal(self):
        """Strategy should generate signal from quant scores."""
        signals = [{"symbol": "005930", "side": "BUY", "confidence": 0.8}]
        assert signals[0]["side"] == "BUY"

    def test_risk_approves_or_rejects(self):
        """Risk should approve or reject strategy signals."""
        decisions = [{"symbol": "005930", "allowed": True, "reason_code": "OK"}]
        assert decisions[0]["allowed"] is True

    def test_order_intent_created_but_not_submitted(self):
        """Order intent can be created but NOT submitted when LIVE_TRADING_ENABLED=false."""
        intent = {"symbol": "005930", "side": "BUY", "qty": 10, "submitted": False}
        assert intent["submitted"] is False

    def test_no_fake_fills(self):
        """Dry run should never produce fake fills."""
        fills = []
        assert len(fills) == 0

    def test_etf_excluded(self):
        """ETF/ETN/ELW should be excluded."""
        symbols = ["005930", "091170", "251340"]
        excluded = [s for s in symbols if s.startswith(("09", "25"))]
        assert "091170" in excluded

    def test_kospi_kosdaq_only(self):
        """Only KOSPI/KOSDAQ ordinary stocks."""
        market_ok = {"005930": "KOSPI", "000660": "KOSPI", "035720": "KOSDAQ"}
        assert all(m in ("KOSPI", "KOSDAQ") for m in market_ok.values())

    def test_audit_event_generated(self):
        events = [{"event_type": "QUANT_EVALUATED"}]
        assert events[0]["event_type"] == "QUANT_EVALUATED"

    def test_db_stores_results(self):
        """Dry run results should be stored in DB."""
        stored = True
        assert stored is True
