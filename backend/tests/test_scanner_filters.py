"""Tests for Common Filters and Scanner Type-specific Quantitative Filters"""
from __future__ import annotations

from scanner.scanner_types import ScannerType, ExclusionReason
from scanner.filters import (
    check_common_filters,
    check_rapid_surge,
    check_liquidity_momentum,
    check_breakout,
    check_pullback_rebound,
)


def _common_valid_metrics() -> dict:
    """공통 필터를 통과하는 기본 metric"""
    return {
        "current_price": 50000,
        "trading_value": 10_000_000_000,
        "volume": 500_000,
        "spread_rate": 0.05,
        "is_trading_halted": False,
        "is_management_issue": False,
        "is_investment_warning": False,
    }


#
# ── 공통 필터 ──
#


class TestCommonFilters:
    """공통 정량 필터 통과/실패"""

    def test_passes_all_common_filters(self):
        result = check_common_filters(_common_valid_metrics())
        assert result.included is True
        assert result.excluded_reason is None

    def test_price_too_high(self):
        metrics = _common_valid_metrics()
        metrics["current_price"] = 3_000_000  # max 기본값 1,000,000
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.PRICE_TOO_HIGH.value

    def test_price_too_low(self):
        metrics = _common_valid_metrics()
        metrics["current_price"] = 50  # min 기본값 100
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.PRICE_TOO_LOW.value

    def test_trading_value_too_low(self):
        metrics = _common_valid_metrics()
        metrics["trading_value"] = 10_000_000  # min 500,000,000
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.TRADING_VALUE_TOO_LOW.value

    def test_volume_too_low(self):
        metrics = _common_valid_metrics()
        metrics["volume"] = 500  # min 10,000
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.VOLUME_TOO_LOW.value

    def test_spread_too_wide(self):
        metrics = _common_valid_metrics()
        metrics["spread_rate"] = 2.0  # max 1.0
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.SPREAD_TOO_WIDE.value

    def test_trading_halted(self):
        metrics = _common_valid_metrics()
        metrics["is_trading_halted"] = True
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.TRADING_HALTED.value

    def test_management_issue(self):
        metrics = _common_valid_metrics()
        metrics["is_management_issue"] = True
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.MANAGEMENT_ISSUE.value

    def test_investment_warning(self):
        metrics = _common_valid_metrics()
        metrics["is_investment_warning"] = True
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.INVESTMENT_WARNING.value

    def test_missing_current_price(self):
        metrics = _common_valid_metrics()
        del metrics["current_price"]
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.DATA_UNAVAILABLE.value

    def test_custom_config(self):
        """커스텀 설정 전달"""
        config = {"max_price": 200_000}
        metrics = _common_valid_metrics()
        metrics["current_price"] = 150_000
        result = check_common_filters(metrics, config=config)
        assert result.included is True

        # 커스텀 max 초과
        metrics["current_price"] = 250_000
        result = check_common_filters(metrics, config=config)
        assert result.included is False

    def test_missing_trading_value(self):
        metrics = _common_valid_metrics()
        del metrics["trading_value"]
        result = check_common_filters(metrics)
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.DATA_UNAVAILABLE.value

    def test_missing_volume(self):
        metrics = _common_valid_metrics()
        del metrics["volume"]
        result = check_common_filters(metrics)
        assert result.included is False

    def test_exact_boundary_min_price(self):
        metrics = _common_valid_metrics()
        metrics["current_price"] = 100  # min_price와 동일
        result = check_common_filters(metrics)
        assert result.included is True

    def test_exact_boundary_max_price(self):
        metrics = _common_valid_metrics()
        metrics["current_price"] = 1_000_000  # max_price와 동일
        result = check_common_filters(metrics)
        assert result.included is True


#
# ── RAPID_SURGE ──
#


def _rapid_surge_valid() -> dict:
    """RAPID_SURGE 조건을 통과하는 기본 metric"""
    return {
        "intraday_change_rate": 5.0,
        "volume_ratio_vs_recent_avg": 3.0,
        "trading_value": 10_000_000_000,
        "execution_strength": 120.0,
        "spread_rate": 0.05,
        "pullback_from_high": 0.5,
        "vi_status": "INACTIVE",
    }


class TestRapidSurgeFilter:
    """RAPID_SURGE 정량 조건 통과/실패"""

    def test_passes_all_conditions(self):
        result = check_rapid_surge(_rapid_surge_valid())
        assert result.passed is True
        assert result.reason is None

    def test_change_rate_below_min(self):
        metrics = _rapid_surge_valid()
        metrics["intraday_change_rate"] = 1.0  # min 2.0
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_change_rate_above_max(self):
        metrics = _rapid_surge_valid()
        metrics["intraday_change_rate"] = 35.0  # max 30.0
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_volume_burst_below_min(self):
        metrics = _rapid_surge_valid()
        metrics["volume_ratio_vs_recent_avg"] = 1.0  # min 1.5
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_trading_value_too_low(self):
        metrics = _rapid_surge_valid()
        metrics["trading_value"] = 100_000_000  # min 500M
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_execution_strength_below_min(self):
        metrics = _rapid_surge_valid()
        metrics["execution_strength"] = 80.0  # min 100
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_spread_too_wide(self):
        metrics = _rapid_surge_valid()
        metrics["spread_rate"] = 2.0  # max 1.0
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_pullback_too_deep(self):
        metrics = _rapid_surge_valid()
        metrics["pullback_from_high"] = 5.0  # max 3.0
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_vi_active(self):
        metrics = _rapid_surge_valid()
        metrics["vi_status"] = "ACTIVE"
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_vi_status_unknown(self):
        metrics = _rapid_surge_valid()
        metrics["vi_status"] = "UNKNOWN"
        result = check_rapid_surge(metrics)
        assert result.passed is False

    def test_scanner_does_not_create_signals(self):
        result = check_rapid_surge(_rapid_surge_valid())
        assert not hasattr(result, "buy_signal")
        assert not hasattr(result, "sell_signal")
        assert not hasattr(result, "order_intent")

    def test_custom_config(self):
        config = {"min_surge_rate": 3.0, "max_surge_rate": 20.0}
        metrics = _rapid_surge_valid()
        metrics["intraday_change_rate"] = 2.5  # min보다 낮음
        result = check_rapid_surge(metrics, config=config)
        assert result.passed is False

        metrics["intraday_change_rate"] = 4.0
        result = check_rapid_surge(metrics, config=config)
        assert result.passed is True


#
# ── LIQUIDITY_MOMENTUM ──
#


def _liquidity_momentum_valid() -> dict:
    return {
        "trading_value_rank": 30,
        "trading_value": 50_000_000_000,
        "intraday_change_rate": 2.0,
        "volume_ratio_vs_recent_avg": 1.5,
        "current_price": 75000,
        "short_term_moving_average": 70000,
        "spread_rate": 0.03,
    }


class TestLiquidityMomentumFilter:
    """LIQUIDITY_MOMENTUM 정량 조건"""

    def test_passes_all_conditions(self):
        result = check_liquidity_momentum(_liquidity_momentum_valid())
        assert result.passed is True

    def test_trading_value_rank_too_high(self):
        metrics = _liquidity_momentum_valid()
        metrics["trading_value_rank"] = 200  # max 100
        result = check_liquidity_momentum(metrics)
        assert result.passed is False

    def test_trading_value_too_low(self):
        metrics = _liquidity_momentum_valid()
        metrics["trading_value"] = 10_000_000_000  # min 20B
        result = check_liquidity_momentum(metrics)
        assert result.passed is False

    def test_change_rate_below_min(self):
        metrics = _liquidity_momentum_valid()
        metrics["intraday_change_rate"] = -1.0  # min 0.5
        result = check_liquidity_momentum(metrics)
        assert result.passed is False

    def test_change_rate_above_max(self):
        metrics = _liquidity_momentum_valid()
        metrics["intraday_change_rate"] = 8.0  # max 5.0
        result = check_liquidity_momentum(metrics)
        assert result.passed is False

    def test_volume_ratio_below_min(self):
        metrics = _liquidity_momentum_valid()
        metrics["volume_ratio_vs_recent_avg"] = 0.8  # min 1.2
        result = check_liquidity_momentum(metrics)
        assert result.passed is False

    def test_price_below_ma(self):
        metrics = _liquidity_momentum_valid()
        metrics["current_price"] = 68000
        metrics["short_term_moving_average"] = 70000
        result = check_liquidity_momentum(metrics)
        assert result.passed is False

    def test_spread_too_wide(self):
        metrics = _liquidity_momentum_valid()
        metrics["spread_rate"] = 0.5  # tight max 0.3
        result = check_liquidity_momentum(metrics)
        assert result.passed is False


#
# ── BREAKOUT ──
#


def _breakout_valid() -> dict:
    return {
        "current_price": 50000,
        "intraday_high": 51000,
        "recent_high_20d": 49000,
        "volume_ratio_vs_recent_avg": 2.5,
        "trading_value": 10_000_000_000,
        "execution_strength": 150.0,
        "market_regime": "BULL",
    }


class TestBreakoutFilter:
    """BREAKOUT 정량 조건"""

    def test_passes_all_conditions(self):
        result = check_breakout(_breakout_valid())
        assert result.passed is True

    def test_not_near_intraday_high(self):
        metrics = _breakout_valid()
        metrics["current_price"] = 40000  # 0.95 * 51000 = 48450보다 낮음
        result = check_breakout(metrics)
        assert result.passed is False

    def test_not_near_20d_high(self):
        metrics = _breakout_valid()
        metrics["current_price"] = 40000  # 0.95 * 49000 = 46550보다 낮음
        result = check_breakout(metrics)
        assert result.passed is False

    def test_volume_ratio_below_min(self):
        metrics = _breakout_valid()
        metrics["volume_ratio_vs_recent_avg"] = 1.0  # min 1.5
        result = check_breakout(metrics)
        assert result.passed is False

    def test_trading_value_too_low(self):
        metrics = _breakout_valid()
        metrics["trading_value"] = 100_000_000  # min 500M
        result = check_breakout(metrics)
        assert result.passed is False

    def test_execution_strength_below_min(self):
        metrics = _breakout_valid()
        metrics["execution_strength"] = 80.0  # min 120
        result = check_breakout(metrics)
        assert result.passed is False

    def test_market_regime_bear(self):
        metrics = _breakout_valid()
        metrics["market_regime"] = "BEAR"
        result = check_breakout(metrics)
        assert result.passed is False

    def test_market_regime_unknown(self):
        metrics = _breakout_valid()
        metrics["market_regime"] = "UNKNOWN"
        result = check_breakout(metrics)
        assert result.passed is False

    def test_market_regime_neutral_allowed(self):
        metrics = _breakout_valid()
        metrics["market_regime"] = "NEUTRAL"
        result = check_breakout(metrics)
        assert result.passed is True


#
# ── PULLBACK_REBOUND ──
#


def _pullback_valid() -> dict:
    return {
        "prior_intraday_gain": 5.0,
        "pullback_from_high": 2.0,
        "rebound_volume_ratio": 1.5,
        "support_holding_score": 7.0,
        "spread_rate": 0.05,
        "trading_value": 10_000_000_000,
    }


class TestPullbackReboundFilter:
    """PULLBACK_REBOUND 정량 조건"""

    def test_passes_all_conditions(self):
        result = check_pullback_rebound(_pullback_valid())
        assert result.passed is True

    def test_prior_gain_below_min(self):
        metrics = _pullback_valid()
        metrics["prior_intraday_gain"] = 1.0  # min 3.0
        result = check_pullback_rebound(metrics)
        assert result.passed is False

    def test_pullback_too_shallow(self):
        metrics = _pullback_valid()
        metrics["pullback_from_high"] = 0.5  # min 1.0
        result = check_pullback_rebound(metrics)
        assert result.passed is False

    def test_pullback_too_deep(self):
        metrics = _pullback_valid()
        metrics["pullback_from_high"] = 8.0  # max 5.0
        result = check_pullback_rebound(metrics)
        assert result.passed is False

    def test_rebound_volume_too_low(self):
        metrics = _pullback_valid()
        metrics["rebound_volume_ratio"] = 0.5  # min 1.0
        result = check_pullback_rebound(metrics)
        assert result.passed is False

    def test_support_holding_too_low(self):
        metrics = _pullback_valid()
        metrics["support_holding_score"] = 2.0  # min 5.0
        result = check_pullback_rebound(metrics)
        assert result.passed is False

    def test_spread_too_wide(self):
        metrics = _pullback_valid()
        metrics["spread_rate"] = 2.0  # max 1.0
        result = check_pullback_rebound(metrics)
        assert result.passed is False

    def test_trading_value_too_low(self):
        metrics = _pullback_valid()
        metrics["trading_value"] = 100_000_000  # min 500M
        result = check_pullback_rebound(metrics)
        assert result.passed is False