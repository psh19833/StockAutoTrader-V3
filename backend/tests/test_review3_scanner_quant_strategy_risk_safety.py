"""3차 코드리뷰 보완 - Scanner/Quant/Strategy/Risk 안전성 테스트"""

from __future__ import annotations

import pytest

from market_regime.regime_result import MarketRegimeResult
from market_regime.regime_score import MarketRegimeScore
from market_regime.regime_state import MarketRegime
from session.session_state import TradingSessionState


def _make_regime(**kwargs):
    defaults = dict(
        regime=MarketRegime.BULL,
        score=MarketRegimeScore(),
        total_score=80.0,
        allow_new_buy=True,
        min_candidate_score_required=50.0,
        candidate_score_adjustment=0.0,
        data_quality_warnings=(),
    )
    defaults.update(kwargs)
    return MarketRegimeResult(**defaults)


def _make_candidate(**kwargs):
    from scanner.candidate import ScannerCandidate
    from scanner.scanner_types import ScannerType
    defaults = dict(
        symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
        scanner_type=ScannerType.BREAKOUT, included=True,
        metrics={"current_price": 70000, "trading_value": 100_000_000_000,
                 "volume": 10_000_000, "spread_rate": 0.01,
                 "is_trading_halted": False, "is_management_issue": False,
                 "is_investment_warning": False, "intraday_change_rate": 5.0,
                 "execution_strength": 500, "volatility_ratio": 0.3,
                 "intraday_high": 70000, "volume_ratio_vs_recent_avg": 5.0,
                 "market_regime": "BULL"},
    )
    defaults.update(kwargs)
    return ScannerCandidate(**defaults)


def _make_buy_signal(symbol="005930"):
    from strategy.signal import StrategySignal
    from strategy.strategy_types import StrategyType
    return StrategySignal(
        signal_id="sig_test", correlation_id="corr_test",
        symbol=symbol, side="BUY",
        strategy_type=StrategyType.BREAKOUT_FOLLOW,
        confidence=0.9, source_quant_id="q123",
        scanner_type="BREAKOUT", market_regime="BULL",
    )


def _make_ctx(warnings=(), positions=frozenset(), emergency_stop=False,
              live_trading=True, session=TradingSessionState.REGULAR_MARKET):
    from risk.risk_context import RiskContext
    return RiskContext(
        market_regime_result=_make_regime(),
        session_state=session,
        emergency_stop=emergency_stop,
        live_trading_enabled=live_trading,
        current_positions=positions,
        pending_orders=frozenset(),
        today_realized_pnl=0,
        daily_loss_limit=10_000_000,
        data_quality_warnings=warnings,
    )


class TestScannerExcludedCandidateQuantReject:
    def test_excluded_candidate_always_reject(self):
        from scanner.candidate import ScannerCandidate
        from scanner.scanner_types import ScannerType
        from quant.scoring_calculator import evaluate_candidate
        from quant.candidate_score import QuantDecision
        candidate = ScannerCandidate(
            symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.BREAKOUT, included=False,
            excluded_reason="ETF_EXCLUDED",
            metrics={"current_price": 70000, "trading_value": 10_000_000_000,
                     "volume": 1_000_000, "spread_rate": 0.1,
                     "is_trading_halted": False, "is_management_issue": False,
                     "is_investment_warning": False,
                     "intraday_change_rate": 5.0, "execution_strength": 300,
                     "volatility_ratio": 0.5, "market_regime": "BULL"},
        )
        score = evaluate_candidate(candidate, _make_regime())
        assert score.decision == QuantDecision.REJECT
        assert "SCANNER_EXCLUDED" in score.reasons
        assert "ETF_EXCLUDED" in score.reasons
        assert score.final_score == 0.0

    def test_excluded_never_creates_signal(self):
        from scanner.candidate import ScannerCandidate
        from scanner.scanner_types import ScannerType
        from quant.scoring_calculator import evaluate_candidate
        from quant.candidate_score import QuantDecision
        from strategy.strategy_evaluator import evaluate_entry
        candidate = ScannerCandidate(
            symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.BREAKOUT, included=False,
            excluded_reason="PRICE_TOO_LOW",
            metrics={"market_regime": "BULL"},
        )
        score = evaluate_candidate(candidate, _make_regime())
        assert score.decision == QuantDecision.REJECT
        result = evaluate_entry(score, _make_regime())
        assert result is None


class TestScannerMarketRegimePassthrough:
    def _make_stock(self, **extra):
        base = {
            "symbol": "005930", "market": "KOSPI", "product_type": "COMMON_STOCK",
            "source": "KIS_API",
            "current_price": 70000, "trading_value": 100_000_000_000,
            "volume": 10_000_000, "spread_rate": 0.01,
            "intraday_high": 71000, "recent_high_20d": 69000,
            "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500,
            "is_trading_halted": False, "is_management_issue": False,
            "is_investment_warning": False,
        }
        base.update(extra)
        return base

    def test_breakout_with_bull(self):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        stocks = [self._make_stock()]
        result = run_scanner(stocks, ScannerType.BREAKOUT, market_regime="BULL")
        assert result.included_count >= 1

    def test_breakout_blocked_by_unknown(self):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        stocks = [self._make_stock()]
        result = run_scanner(stocks, ScannerType.BREAKOUT, market_regime="UNKNOWN")
        assert result.included_count == 0

    def test_breakout_blocked_by_bear(self):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        stocks = [self._make_stock()]
        result = run_scanner(stocks, ScannerType.BREAKOUT, market_regime="BEAR")
        assert result.included_count == 0

    def test_market_regime_injected(self):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        stocks = [self._make_stock()]
        result = run_scanner(stocks, ScannerType.BREAKOUT, market_regime="BULL")
        assert result.included_count >= 1
class TestScannerCandidatePreservesOriginal:
    def _run(self, **stock):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        default = {
            "symbol": "005930", "source": "KIS_API",
            "current_price": 70000, "trading_value": 100_000_000_000,
            "volume": 10_000_000, "spread_rate": 0.01,
            "intraday_high": 71000, "recent_high_20d": 69000,
            "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500,
            "is_trading_halted": False, "is_management_issue": False,
            "is_investment_warning": False,
        }
        default.update(stock)
        return run_scanner([default], ScannerType.BREAKOUT, market_regime="BULL")

    def test_etf_preserves_product_type(self):
        result = self._run(market="KOSPI", product_type="ETF")
        candidates = list(result.candidates)
        assert len(candidates) > 0
        c = candidates[0]
        assert c.product_type == "ETF"
        assert c.included is False

    def test_unknown_preserves_product_type(self):
        result = self._run(market="KOSPI", product_type="UNKNOWN")
        candidates = list(result.candidates)
        assert len(candidates) > 0
        c = candidates[0]
        assert c.product_type == "UNKNOWN"

    def test_non_kospi_preserves_market(self):
        result = self._run(market="NASDAQ", product_type="COMMON_STOCK")
        candidates = list(result.candidates)
        assert len(candidates) > 0
        c = candidates[0]
        assert c.market == "NASDAQ"

    def test_normal_common_stock_passes(self):
        result = self._run(market="KOSPI", product_type="COMMON_STOCK")
        assert result.included_count >= 1
class TestMalformedMetricDefense:
    def _run(self, **metrics):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        full = {
            "is_trading_halted": False, "is_management_issue": False,
            "is_investment_warning": False,
            "intraday_high": 71000, "recent_high_20d": 69000,
            "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500,
        }
        full.update(metrics)
        full.update({"symbol": "005930", "market": "KOSPI",
                     "product_type": "COMMON_STOCK", "source": "KIS_API"})
        stocks = [full]
        return run_scanner(stocks, ScannerType.BREAKOUT, market_regime="BULL")

    def test_dash_price_no_crash(self):
        result = self._run(current_price="-", trading_value=100_000_000_000,
                           volume=10_000_000)
        assert result.included_count + result.excluded_count >= 1

    def test_na_trading_value_no_crash(self):
        result = self._run(current_price=70000, trading_value="N/A",
                           volume=10_000_000)
        assert result.included_count + result.excluded_count >= 1

    def test_empty_volume_no_crash(self):
        result = self._run(current_price=70000, trading_value=100_000_000_000,
                           volume="")
        assert result.included_count + result.excluded_count >= 1

    def test_malformed_and_normal_together(self):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        stocks = [
            {"symbol": "BAD", "market": "KOSPI", "product_type": "COMMON_STOCK",
             "source": "KIS_API",
             "current_price": "-", "is_trading_halted": False,
             "is_management_issue": False, "is_investment_warning": False,
             "intraday_high": 71000, "recent_high_20d": 69000,
             "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500},
            {"symbol": "GOOD", "market": "KOSPI", "product_type": "COMMON_STOCK",
             "source": "KIS_API",
             "current_price": 70000, "trading_value": 100_000_000_000,
             "volume": 10_000_000, "spread_rate": 0.01,
             "intraday_high": 71000, "recent_high_20d": 69000,
             "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500,
             "is_trading_halted": False, "is_management_issue": False,
             "is_investment_warning": False},
        ]
        result = run_scanner(stocks, ScannerType.BREAKOUT, market_regime="BULL")
        assert result.included_count + result.excluded_count >= 2
class TestQuantDataQualityWarningsBlock:
    def test_stale_orderbook_reject(self):
        from quant.scoring_calculator import evaluate_candidate
        from quant.candidate_score import QuantDecision
        score = evaluate_candidate(_make_candidate(),
                                   _make_regime(data_quality_warnings=("STALE_ORDERBOOK",)))
        assert score.decision == QuantDecision.REJECT
        assert "DATA_QUALITY_BLOCKED" in score.reasons

    def test_ws_disconnected_reject(self):
        from quant.scoring_calculator import evaluate_candidate
        from quant.candidate_score import QuantDecision
        score = evaluate_candidate(_make_candidate(),
                                   _make_regime(data_quality_warnings=("WS_DISCONNECTED",)))
        assert score.decision == QuantDecision.REJECT

    def test_kis_query_failed_reject(self):
        from quant.scoring_calculator import evaluate_candidate
        from quant.candidate_score import QuantDecision
        score = evaluate_candidate(_make_candidate(),
                                   _make_regime(data_quality_warnings=("KIS_QUERY_FAILED",)))
        assert score.decision == QuantDecision.REJECT

    def test_no_warnings_can_pass(self):
        from quant.scoring_calculator import evaluate_candidate
        from quant.candidate_score import QuantDecision
        score = evaluate_candidate(_make_candidate(), _make_regime())
        assert score.decision != QuantDecision.REJECT or (
            "DATA_QUALITY_BLOCKED" not in score.reasons
        )


class TestNegativeMomentumPenalty:
    def test_negative_change_does_not_boost(self):
        from quant.scoring_calculator import evaluate_candidate
        candidate = _make_candidate(metrics={
            "current_price": 70000, "trading_value": 100_000_000_000,
            "volume": 10_000_000, "spread_rate": 0.01,
            "is_trading_halted": False, "is_management_issue": False,
            "is_investment_warning": False, "intraday_change_rate": -7.0,
            "execution_strength": 500, "volatility_ratio": 0.3,
            "intraday_high": 70000, "volume_ratio_vs_recent_avg": 5.0,
            "market_regime": "BULL",
        })
        score = evaluate_candidate(candidate, _make_regime())
        assert score.momentum_score <= 5.0, f"momentum_score={score.momentum_score}"  # exec_score=10/2=5 max

    def test_positive_change_boosts(self):
        from quant.scoring_calculator import evaluate_candidate
        candidate = _make_candidate()
        score = evaluate_candidate(candidate, _make_regime())
        assert score.momentum_score > 0

    def test_zero_change_conservative(self):
        from quant.scoring_calculator import evaluate_candidate
        candidate = _make_candidate(metrics={
            "current_price": 70000, "trading_value": 100_000_000_000,
            "volume": 10_000_000, "spread_rate": 0.01,
            "is_trading_halted": False, "is_management_issue": False,
            "is_investment_warning": False, "intraday_change_rate": 0.0,
            "execution_strength": 500, "volatility_ratio": 0.3,
            "intraday_high": 70000, "volume_ratio_vs_recent_avg": 5.0,
            "market_regime": "BULL",
        })
        score = evaluate_candidate(candidate, _make_regime())
        # With zero change and exec_strength=500, exec_score = 10, momentum = (0+10)/2 = 5
        assert score.momentum_score == 5.0, f"momentum_score={score.momentum_score}"


class TestRiskDataQualityBlock:
    def test_data_quality_rejects(self):
        from risk.risk_engine import evaluate_risk
        sig = _make_buy_signal()
        ctx = _make_ctx(warnings=("STALE_ORDERBOOK",))
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000)
        assert not decision.allowed
        assert "data_quality_warnings" in decision.failed_items

    def test_no_warnings_allows(self):
        from risk.risk_engine import evaluate_risk
        sig = _make_buy_signal()
        ctx = _make_ctx(warnings=())
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000)
        assert decision.allowed

    def test_reason_is_data_quality(self):
        from risk.risk_engine import evaluate_risk
        sig = _make_buy_signal()
        ctx = _make_ctx(warnings=("STALE_QUOTE",))
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000)
        assert "DATA_QUALITY_BLOCKED" in decision.reason_code or                "data_quality" in decision.reason_text.lower()


class TestRiskLimits:
    def test_amount_exceeds_limit_rejects(self):
        from risk.risk_engine import evaluate_risk
        from risk.risk_config import RiskLimits
        sig = _make_buy_signal()
        ctx = _make_ctx()
        limits = RiskLimits(max_amount_per_symbol=5_000_000)
        decision = evaluate_risk(sig, ctx, requested_amount=10_000_000, limits=limits)
        assert not decision.allowed
        assert "amount_limit" in decision.failed_items

    def test_position_count_exceeded_rejects_buy(self):
        from risk.risk_engine import evaluate_risk
        from risk.risk_config import RiskLimits
        sig = _make_buy_signal(symbol="NEW")
        ctx = _make_ctx(positions=frozenset({"A", "B", "C", "D", "E"}))
        limits = RiskLimits(max_position_count=5)
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000, limits=limits)
        assert not decision.allowed
        assert "position_limit" in decision.failed_items

    def test_sell_not_blocked_by_position_limit(self):
        from risk.risk_engine import evaluate_risk
        from risk.risk_config import RiskLimits
        from strategy.signal import StrategySignal
        from strategy.strategy_types import StrategyType
        sig = StrategySignal(
            signal_id="sig_sell", correlation_id="corr_sell",
            symbol="A", side="SELL",
            strategy_type=StrategyType.FAST_EXIT,
            confidence=1.0, source_quant_id="q1",
            scanner_type="FAST_EXIT", market_regime="BULL",
        )
        ctx = _make_ctx(positions=frozenset({"A", "B", "C", "D", "E"}))
        limits = RiskLimits(max_position_count=5)
        decision = evaluate_risk(sig, ctx, requested_amount=0, limits=limits)
        assert decision.allowed

    def test_requested_amount_recorded(self):
        from risk.risk_engine import evaluate_risk
        sig = _make_buy_signal()
        ctx = _make_ctx()
        decision = evaluate_risk(sig, ctx, requested_amount=3_000_000)
        assert decision.requested_amount == 3_000_000

    def test_default_limits_used_when_none(self):
        from risk.risk_engine import evaluate_risk
        sig = _make_buy_signal()
        ctx = _make_ctx()
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000, limits=None)
        assert decision.allowed


class TestFailedItemsAllPreserved:
    def test_multiple_failures_all_recorded(self):
        from risk.risk_engine import evaluate_risk
        from strategy.signal import StrategySignal
        from strategy.strategy_types import StrategyType
        ctx = _make_ctx(warnings=("KIS_QUERY_FAILED",), emergency_stop=True,
                        live_trading=False,
                        session=TradingSessionState.CLOSED_HOLIDAY)
        sig = StrategySignal(
            signal_id="sig_test", correlation_id="corr_test",
            symbol="005930", side="BUY",
            strategy_type=StrategyType.BREAKOUT_FOLLOW,
            confidence=0.9, source_quant_id="q123",
            scanner_type="BREAKOUT", market_regime="BULL",
        )
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000)
        assert not decision.allowed
        assert len(decision.failed_items) >= 3
        assert "live_trading_enabled" in decision.failed_items
        assert "emergency_stop" in decision.failed_items
        assert "session_state" in decision.failed_items

    def test_checked_items_has_all_checks(self):
        from risk.risk_engine import evaluate_risk
        sig = _make_buy_signal()
        ctx = _make_ctx()
        decision = evaluate_risk(sig, ctx, requested_amount=1_000_000)
        assert len(decision.checked_items) >= 8


class TestSourceEndpointsPerCandidate:
    def test_candidates_have_own_endpoints(self):
        from scanner.scanner_engine import run_scanner
        from scanner.scanner_types import ScannerType
        stocks = [
            {"symbol": "A", "market": "KOSPI", "product_type": "COMMON_STOCK",
             "source": "KIS_API",
             "source_endpoints": frozenset({"price"}),
             "current_price": 70000, "trading_value": 100_000_000_000,
             "volume": 10_000_000, "spread_rate": 0.01,
             "intraday_high": 71000, "recent_high_20d": 69000,
             "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500,
             "is_trading_halted": False, "is_management_issue": False,
             "is_investment_warning": False},
            {"symbol": "B", "market": "KOSPI", "product_type": "COMMON_STOCK",
             "source": "KIS_API",
             "source_endpoints": frozenset({"stock_info"}),
             "current_price": 50000, "trading_value": 50_000_000_000,
             "volume": 5_000_000, "spread_rate": 0.02,
             "intraday_high": 51000, "recent_high_20d": 49000,
             "volume_ratio_vs_recent_avg": 5.0, "execution_strength": 500,
             "is_trading_halted": False, "is_management_issue": False,
             "is_investment_warning": False},
        ]
        result = run_scanner(stocks, ScannerType.BREAKOUT, market_regime="BULL")
        if result.included_count >= 1:
            for idx, c in enumerate(result.candidates):
                if c.symbol == "B":
                    assert "price" not in c.source_endpoints
                if c.symbol == "A":
                    assert "stock_info" not in c.source_endpoints
class TestStrategyDataQualityBlock:
    def test_data_quality_warnings_blocks_signal(self):
        from quant.candidate_score import QuantCandidateScore, QuantDecision
        from strategy.strategy_evaluator import evaluate_entry
        score = QuantCandidateScore(
            symbol="005930", scanner_type="BREAKOUT",
            scan_run_id="sr1", evaluation_id="ev1",
            final_score=70.0, decision=QuantDecision.PASS,
            reasons=(), data_quality_warnings=("STALE_ORDERBOOK",),
            liquidity_score=8.0, spread_score=8.0, momentum_score=8.0,
            symbol_risk_penalty=0.0,
        )
        signal = evaluate_entry(score, _make_regime())
        assert signal is None

    def test_no_warnings_creates_signal(self):
        from quant.candidate_score import QuantCandidateScore, QuantDecision
        from strategy.strategy_evaluator import evaluate_entry
        score = QuantCandidateScore(
            symbol="005930", scanner_type="BREAKOUT",
            scan_run_id="sr1", evaluation_id="ev1",
            final_score=70.0, decision=QuantDecision.PASS,
            liquidity_score=8.0, spread_score=8.0, momentum_score=8.0,
            symbol_risk_penalty=0.0, reasons=(), data_quality_warnings=(),
        )
        signal = evaluate_entry(score, _make_regime())
        assert signal is not None
        assert signal.side == "BUY"
