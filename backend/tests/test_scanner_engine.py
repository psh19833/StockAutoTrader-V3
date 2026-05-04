"""Tests for Scanner Engine — orchestration layer"""
from __future__ import annotations

import pytest

from scanner.scanner_types import ScannerType, ExclusionReason
from scanner.scanner_engine import run_scanner, run_all_scanners


# ── Helper: build minimal stock input ──

def _make_stock(symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
                source="KIS_API", **metrics):
    return {
        "symbol": symbol,
        "symbol_name": f"Stock_{symbol}",
        "market": market,
        "product_type": product_type,
        "source": source,
        **metrics,
    }


def _make_rapid_surge_stock():
    return _make_stock(
        symbol="005930",
        intraday_change_rate=5.0,
        volume_ratio_vs_recent_avg=3.0,
        trading_value=50_000_000_000,
        execution_strength=150.0,
        spread_rate=0.1,
        pullback_from_high=1.0,
        vi_status="NONE",
        current_price=75000.0,
        volume=10_000_000,
        is_trading_halted=False,
        is_management_issue=False,
        is_investment_warning=False,
    )


def _make_liquidity_stock():
    return _make_stock(
        symbol="000660",
        trading_value_rank=10,
        trading_value=100_000_000_000,
        intraday_change_rate=2.0,
        volume_ratio_vs_recent_avg=1.5,
        short_term_moving_average=70000.0,
        spread_rate=0.1,
        current_price=75000.0,
        volume=10_000_000,
        is_trading_halted=False,
        is_management_issue=False,
        is_investment_warning=False,
    )


class TestRunScannerSingle:
    """단일 Scanner Type 실행"""

    def test_rapid_surge_included(self):
        stocks = [_make_rapid_surge_stock()]
        result = run_scanner(stocks, ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.scanner_type == ScannerType.RAPID_SURGE
        assert result.included_count == 1
        assert result.collected_count == 1
        assert len(result.candidates) == 1
        assert result.candidates[0].included is True

    def test_rapid_surge_excluded_universe(self):
        """ETF는 Universe에서 제외된다"""
        stock = _make_rapid_surge_stock()
        stock["product_type"] = "ETF"
        result = run_scanner([stock], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.included_count == 0
        assert result.excluded_count == 1
        assert result.candidates[0].excluded_reason == ExclusionReason.ETF_EXCLUDED.value

    def test_rapid_surge_excluded_common_filter(self):
        """거래중단은 공통 필터에서 제외된다"""
        stock = _make_rapid_surge_stock()
        stock["is_trading_halted"] = True
        result = run_scanner([stock], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.included_count == 0
        assert result.candidates[0].excluded_reason == ExclusionReason.TRADING_HALTED.value

    def test_rapid_surge_excluded_scanner_filter(self):
        """등락률 미달이면 Scanner 필터에서 제외된다"""
        stock = _make_rapid_surge_stock()
        stock["intraday_change_rate"] = 0.5  # below min_surge_rate 2.0
        result = run_scanner([stock], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.included_count == 0
        assert "surge_rate" in result.candidates[0].excluded_reason.lower()

    def test_liquidity_momentum_included(self):
        stocks = [_make_liquidity_stock()]
        result = run_scanner(stocks, ScannerType.LIQUIDITY_MOMENTUM, market_regime="NEUTRAL")
        assert result.included_count == 1
        assert result.scanner_type == ScannerType.LIQUIDITY_MOMENTUM

    def test_breakout_included_in_bull(self):
        stock = _make_stock(
            symbol="035420",
            current_price=95000.0,
            intraday_high=100000.0,
            recent_high_20d=100000.0,
            volume_ratio_vs_recent_avg=3.0,
            trading_value=50_000_000_000,
            execution_strength=150.0,
            market_regime="BULL",
            spread_rate=0.1,
            volume=10_000_000,
            is_trading_halted=False,
            is_management_issue=False,
            is_investment_warning=False,
        )
        result = run_scanner([stock], ScannerType.BREAKOUT, market_regime="BULL")
        assert result.included_count == 1

    def test_breakout_excluded_in_bear(self):
        stock = _make_stock(
            symbol="035420",
            current_price=95000.0,
            intraday_high=100000.0,
            recent_high_20d=100000.0,
            volume_ratio_vs_recent_avg=3.0,
            trading_value=50_000_000_000,
            execution_strength=150.0,
            market_regime="BEAR",
            spread_rate=0.1,
            volume=10_000_000,
            is_trading_halted=False,
            is_management_issue=False,
            is_investment_warning=False,
        )
        result = run_scanner([stock], ScannerType.BREAKOUT, market_regime="BEAR")
        assert result.included_count == 0

    def test_pullback_rebound_included(self):
        stock = _make_stock(
            symbol="035720",
            prior_intraday_gain=5.0,
            pullback_from_high=2.0,
            rebound_volume_ratio=2.0,
            support_holding_score=7.0,
            spread_rate=0.2,
            trading_value=10_000_000_000,
            current_price=50000.0,
            volume=5_000_000,
            is_trading_halted=False,
            is_management_issue=False,
            is_investment_warning=False,
        )
        result = run_scanner([stock], ScannerType.PULLBACK_REBOUND, market_regime="NEUTRAL")
        assert result.included_count == 1

    def test_empty_input(self):
        result = run_scanner([], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.collected_count == 0
        assert result.included_count == 0
        assert result.excluded_count == 0

    def test_multiple_stocks_mixed(self):
        rapid = _make_rapid_surge_stock()
        etf = _make_rapid_surge_stock()
        etf["symbol"] = "999999"
        etf["product_type"] = "ETF"
        result = run_scanner([rapid, etf], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.collected_count == 2
        assert result.included_count == 1
        assert result.excluded_count == 1

    def test_candidate_excluded_reason_set(self):
        stock = _make_rapid_surge_stock()
        stock["product_type"] = "ETN"
        result = run_scanner([stock], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.candidates[0].excluded_reason is not None
        assert result.candidates[0].included is False


class TestRunAllScanners:
    """전체 Scanner 실행"""

    def test_run_all_produces_all_types(self):
        stocks = [
            _make_rapid_surge_stock(),
            _make_liquidity_stock(),
            _make_stock(
                symbol="035420", current_price=95000.0, intraday_high=100000.0,
                recent_high_20d=100000.0, volume_ratio_vs_recent_avg=3.0,
                trading_value=50_000_000_000, execution_strength=150.0,
                market_regime="BULL", spread_rate=0.1, volume=10_000_000,
                is_trading_halted=False, is_management_issue=False,
                is_investment_warning=False,
            ),
            _make_stock(
                symbol="035720", prior_intraday_gain=5.0, pullback_from_high=2.0,
                rebound_volume_ratio=2.0, support_holding_score=7.0,
                spread_rate=0.2, trading_value=10_000_000_000,
                current_price=50000.0, volume=5_000_000,
                is_trading_halted=False, is_management_issue=False,
                is_investment_warning=False,
            ),
        ]
        results = run_all_scanners(stocks, market_regime="BULL")
        assert len(results) == 4
        scanner_types = {r.scanner_type for r in results}
        assert ScannerType.RAPID_SURGE in scanner_types
        assert ScannerType.LIQUIDITY_MOMENTUM in scanner_types
        assert ScannerType.BREAKOUT in scanner_types
        assert ScannerType.PULLBACK_REBOUND in scanner_types

    def test_run_all_respects_market_regime(self):
        """BEAR 시장에서 BREAKOUT+RAPID_SURGE는 제한"""
        stocks = [
            _make_rapid_surge_stock(),
            _make_liquidity_stock(),
        ]
        results = run_all_scanners(stocks, market_regime="BEAR")
        # All 4 scanner types run, but BEAR regime affects filtering
        assert len(results) == 4

    def test_no_order_fields_in_results(self):
        """Scanner 결과에 주문 관련 필드 없음"""
        stocks = [_make_rapid_surge_stock()]
        result = run_scanner(stocks, ScannerType.RAPID_SURGE, market_regime="BULL")
        for candidate in result.candidates:
            metrics_keys = set(candidate.metrics.keys())
            forbidden = {"buy_signal", "sell_signal", "order_intent",
                         "quantity", "stop_loss", "take_profit", "order_id"}
            assert not (metrics_keys & forbidden)


class TestScannerExcludedReasonPropagation:
    """Scanner-specific filter 실패 사유가 excluded_reason에 보존되는지"""

    def test_rapid_surge_vi_active_reason(self):
        """RAPID_SURGE: VI_ACTIVE → excluded_reason에 VI 포함"""
        stock = _make_rapid_surge_stock()
        stock["vi_status"] = "ACTIVE"
        result = run_scanner([stock], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.included_count == 0
        assert result.excluded_count == 1
        assert "VI" in result.candidates[0].excluded_reason.upper()

    def test_rapid_surge_spread_too_wide_reason(self):
        """RAPID_SURGE: spread 초과 → excluded_reason에 spread 포함"""
        stock = _make_rapid_surge_stock()
        stock["spread_rate"] = 5.0  # max_spread_rate is 1.0
        result = run_scanner([stock], ScannerType.RAPID_SURGE, market_regime="BULL")
        assert result.included_count == 0
        assert "spread" in result.candidates[0].excluded_reason.lower()

    def test_liquidity_momentum_trading_value_reason(self):
        """LIQUIDITY_MOMENTUM: 거래대금 부족 → excluded_reason에 trading_value 포함"""
        stock = _make_liquidity_stock()
        stock["trading_value"] = 100_000  # far below 20B minimum
        result = run_scanner([stock], ScannerType.LIQUIDITY_MOMENTUM, market_regime="NEUTRAL")
        assert result.included_count == 0
        assert "trading_value" in result.candidates[0].excluded_reason.lower()

    def test_breakout_regime_not_allowed_reason(self):
        """BREAKOUT: Market Regime 부적합 → excluded_reason에 market_regime 포함"""
        stock = _make_stock(
            symbol="035420", current_price=95000.0, intraday_high=100000.0,
            recent_high_20d=100000.0, volume_ratio_vs_recent_avg=3.0,
            trading_value=50_000_000_000, execution_strength=150.0,
            market_regime="BEAR", spread_rate=0.1, volume=10_000_000,
            is_trading_halted=False, is_management_issue=False,
            is_investment_warning=False,
        )
        result = run_scanner([stock], ScannerType.BREAKOUT, market_regime="BEAR")
        assert result.included_count == 0
        assert "market_regime" in result.candidates[0].excluded_reason.lower()

    def test_pullback_rebound_pullback_too_deep_reason(self):
        """PULLBACK_REBOUND: 눌림 깊이 초과 → excluded_reason에 pullback 포함"""
        stock = _make_stock(
            symbol="035720", prior_intraday_gain=5.0,
            pullback_from_high=10.0,  # far exceeds max_pullback_depth of 5.0
            rebound_volume_ratio=2.0, support_holding_score=7.0,
            spread_rate=0.2, trading_value=10_000_000_000,
            current_price=50000.0, volume=5_000_000,
            is_trading_halted=False, is_management_issue=False,
            is_investment_warning=False,
        )
        result = run_scanner([stock], ScannerType.PULLBACK_REBOUND, market_regime="NEUTRAL")
        assert result.included_count == 0
        assert "pullback" in result.candidates[0].excluded_reason.lower()
