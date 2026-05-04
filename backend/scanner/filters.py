"""Scanner Filters — 공통 정량 필터 + Scanner Type별 정량 조건

모든 Scanner는 공통 필터를 먼저 통과해야 하며,
Scanner Type별 정량 조건은 후보 발굴 시 적용된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scanner.scanner_types import ExclusionReason

# ── 공통 필터 기본 설정값 ──

DEFAULT_CONFIG: dict[str, float] = {
    "min_price": 100.0,
    "max_price": 1_000_000.0,
    "min_trading_value": 500_000_000.0,
    "min_volume": 10_000.0,
    "max_spread_rate": 1.0,
}

# ── Scanner Type별 기본 설정값 ──

RAPID_SURGE_DEFAULT_CONFIG: dict[str, float | str] = {
    "min_surge_rate": 2.0,
    "max_surge_rate": 30.0,
    "min_volume_burst_ratio": 1.5,
    "min_trading_value": 500_000_000.0,
    "min_execution_strength": 100.0,
    "max_spread_rate": 1.0,
    "max_pullback_from_high": 3.0,
}

LIQUIDITY_MOMENTUM_DEFAULT_CONFIG: dict[str, float] = {
    "max_trading_value_rank": 100,
    "min_large_trading_value": 20_000_000_000.0,
    "min_momentum_change_rate": 0.5,
    "max_momentum_change_rate": 5.0,
    "min_momentum_volume_ratio": 1.2,
    "tight_spread_rate": 0.3,
}

BREAKOUT_DEFAULT_CONFIG: dict[str, float] = {
    "intraday_high_proximity": 0.95,
    "recent_high_proximity": 0.95,
    "min_breakout_volume_ratio": 1.5,
    "min_trading_value": 500_000_000.0,
    "min_breakout_execution_strength": 120.0,
}

PULLBACK_REBOUND_DEFAULT_CONFIG: dict[str, float] = {
    "min_prior_gain": 3.0,
    "min_pullback_depth": 1.0,
    "max_pullback_depth": 5.0,
    "min_rebound_volume_ratio": 1.0,
    "min_support_holding_score": 5.0,
    "max_spread_rate": 1.0,
    "min_trading_value": 500_000_000.0,
}


@dataclass(frozen=True)
class FilterResult:
    """단일 필터 결과"""
    passed: bool
    reason: str | None = None


@dataclass(frozen=True)
class CommonFilterResult:
    """공통 필터 결과"""
    included: bool
    excluded_reason: str | None = None


# ── 공통 필터 ──


def _get_float(metrics: dict[str, Any], key: str) -> float | None:
    """metrics에서 float 값 추출 (None-safe)"""
    val = metrics.get(key)
    if val is None:
        return None
    return float(val)


def check_common_filters(
    metrics: dict[str, Any],
    config: dict[str, float] | None = None,
) -> CommonFilterResult:
    """Scanner 공통 정량 필터

    모든 scanner_type은 이 필터를 먼저 통과해야 한다.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    required_keys = [
        "current_price", "trading_value", "volume", "spread_rate",
        "is_trading_halted", "is_management_issue", "is_investment_warning",
    ]
    for key in required_keys:
        if key not in metrics or metrics[key] is None:
            return CommonFilterResult(
                included=False,
                excluded_reason=ExclusionReason.DATA_UNAVAILABLE.value,
            )

    price = _get_float(metrics, "current_price")
    trading_value = _get_float(metrics, "trading_value")
    volume = _get_float(metrics, "volume")
    spread_rate = _get_float(metrics, "spread_rate")

    if price is None or price < cfg["min_price"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.PRICE_TOO_LOW.value,
        )
    if price > cfg["max_price"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.PRICE_TOO_HIGH.value,
        )

    if trading_value is None or trading_value < cfg["min_trading_value"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.TRADING_VALUE_TOO_LOW.value,
        )

    if volume is None or volume < cfg["min_volume"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.VOLUME_TOO_LOW.value,
        )

    if spread_rate is None or spread_rate > cfg["max_spread_rate"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.SPREAD_TOO_WIDE.value,
        )

    if metrics["is_trading_halted"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.TRADING_HALTED.value,
        )

    if metrics["is_management_issue"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.MANAGEMENT_ISSUE.value,
        )

    if metrics["is_investment_warning"]:
        return CommonFilterResult(
            included=False,
            excluded_reason=ExclusionReason.INVESTMENT_WARNING.value,
        )

    return CommonFilterResult(included=True)


# ── RAPID_SURGE ──


def check_rapid_surge(
    metrics: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> FilterResult:
    """RAPID_SURGE 정량 조건"""
    cfg = {**RAPID_SURGE_DEFAULT_CONFIG, **(config or {})}

    surge_rate = _get_float(metrics, "intraday_change_rate")
    if surge_rate is None:
        return FilterResult(passed=False, reason="DATA_UNAVAILABLE")

    if surge_rate < cfg["min_surge_rate"]:
        return FilterResult(passed=False, reason=f"surge_rate {surge_rate} < min {cfg['min_surge_rate']}")

    if surge_rate > cfg["max_surge_rate"]:
        return FilterResult(passed=False, reason=f"surge_rate {surge_rate} > max {cfg['max_surge_rate']}")

    volume_ratio = _get_float(metrics, "volume_ratio_vs_recent_avg")
    if volume_ratio is None or volume_ratio < cfg["min_volume_burst_ratio"]:
        return FilterResult(passed=False, reason="volume_burst_ratio too low")

    trading_value = _get_float(metrics, "trading_value")
    if trading_value is None or trading_value < cfg["min_trading_value"]:
        return FilterResult(passed=False, reason="trading_value too low")

    exec_strength = _get_float(metrics, "execution_strength")
    if exec_strength is None or exec_strength < cfg["min_execution_strength"]:
        return FilterResult(passed=False, reason="execution_strength too low")

    spread = _get_float(metrics, "spread_rate")
    if spread is None or spread > cfg["max_spread_rate"]:
        return FilterResult(passed=False, reason="spread too wide")

    pullback = _get_float(metrics, "pullback_from_high")
    if pullback is None or pullback > cfg["max_pullback_from_high"]:
        return FilterResult(passed=False, reason="pullback too deep")

    vi_status = metrics.get("vi_status", "UNKNOWN")
    if vi_status == "ACTIVE":
        return FilterResult(passed=False, reason="VI_ACTIVE")
    if vi_status == "UNKNOWN":
        return FilterResult(passed=False, reason="VI_UNKNOWN")

    return FilterResult(passed=True)


# ── LIQUIDITY_MOMENTUM ──


def check_liquidity_momentum(
    metrics: dict[str, Any],
    config: dict[str, float] | None = None,
) -> FilterResult:
    """LIQUIDITY_MOMENTUM 정량 조건"""
    cfg = {**LIQUIDITY_MOMENTUM_DEFAULT_CONFIG, **(config or {})}

    rank = metrics.get("trading_value_rank")
    if rank is None or float(rank) > cfg["max_trading_value_rank"]:
        return FilterResult(passed=False, reason="trading_value_rank too high")

    trading_value = _get_float(metrics, "trading_value")
    if trading_value is None or trading_value < cfg["min_large_trading_value"]:
        return FilterResult(passed=False, reason="trading_value too low")

    change_rate = _get_float(metrics, "intraday_change_rate")
    if change_rate is None:
        return FilterResult(passed=False, reason="DATA_UNAVAILABLE")
    if change_rate < cfg["min_momentum_change_rate"]:
        return FilterResult(passed=False, reason="change_rate below min")
    if change_rate > cfg["max_momentum_change_rate"]:
        return FilterResult(passed=False, reason="change_rate above max")

    volume_ratio = _get_float(metrics, "volume_ratio_vs_recent_avg")
    if volume_ratio is None or volume_ratio < cfg["min_momentum_volume_ratio"]:
        return FilterResult(passed=False, reason="volume_ratio too low")

    price = _get_float(metrics, "current_price")
    ma = _get_float(metrics, "short_term_moving_average")
    if price is None or ma is None or price <= ma:
        return FilterResult(passed=False, reason="price below moving average")

    spread = _get_float(metrics, "spread_rate")
    if spread is None or spread > cfg["tight_spread_rate"]:
        return FilterResult(passed=False, reason="spread too wide")

    return FilterResult(passed=True)


# ── BREAKOUT ──


def check_breakout(
    metrics: dict[str, Any],
    config: dict[str, float] | None = None,
) -> FilterResult:
    """BREAKOUT 정량 조건"""
    cfg = {**BREAKOUT_DEFAULT_CONFIG, **(config or {})}

    price = _get_float(metrics, "current_price")
    intraday_high = _get_float(metrics, "intraday_high")
    recent_high = _get_float(metrics, "recent_high_20d")

    if price is None or intraday_high is None:
        return FilterResult(passed=False, reason="DATA_UNAVAILABLE")

    if price < intraday_high * cfg["intraday_high_proximity"]:
        return FilterResult(passed=False, reason="not near intraday high")

    if recent_high is None or price < recent_high * cfg["recent_high_proximity"]:
        return FilterResult(passed=False, reason="not near 20d high")

    volume_ratio = _get_float(metrics, "volume_ratio_vs_recent_avg")
    if volume_ratio is None or volume_ratio < cfg["min_breakout_volume_ratio"]:
        return FilterResult(passed=False, reason="breakout volume too low")

    trading_value = _get_float(metrics, "trading_value")
    if trading_value is None or trading_value < cfg["min_trading_value"]:
        return FilterResult(passed=False, reason="trading_value too low")

    exec_strength = _get_float(metrics, "execution_strength")
    if exec_strength is None or exec_strength < cfg["min_breakout_execution_strength"]:
        return FilterResult(passed=False, reason="execution_strength too low")

    market_regime = metrics.get("market_regime", "UNKNOWN")
    if market_regime not in ("BULL", "NEUTRAL"):
        return FilterResult(passed=False, reason=f"market_regime {market_regime} not allowed")

    return FilterResult(passed=True)


# ── PULLBACK_REBOUND ──


def check_pullback_rebound(
    metrics: dict[str, Any],
    config: dict[str, float] | None = None,
) -> FilterResult:
    """PULLBACK_REBOUND 정량 조건"""
    cfg = {**PULLBACK_REBOUND_DEFAULT_CONFIG, **(config or {})}

    prior_gain = _get_float(metrics, "prior_intraday_gain")
    if prior_gain is None or prior_gain < cfg["min_prior_gain"]:
        return FilterResult(passed=False, reason="prior gain too low")

    pullback = _get_float(metrics, "pullback_from_high")
    if pullback is None:
        return FilterResult(passed=False, reason="DATA_UNAVAILABLE")
    if pullback < cfg["min_pullback_depth"]:
        return FilterResult(passed=False, reason="pullback too shallow")
    if pullback > cfg["max_pullback_depth"]:
        return FilterResult(passed=False, reason="pullback too deep")

    rebound_vol = _get_float(metrics, "rebound_volume_ratio")
    if rebound_vol is None or rebound_vol < cfg["min_rebound_volume_ratio"]:
        return FilterResult(passed=False, reason="rebound volume too low")

    support = _get_float(metrics, "support_holding_score")
    if support is None or support < cfg["min_support_holding_score"]:
        return FilterResult(passed=False, reason="support holding too low")

    spread = _get_float(metrics, "spread_rate")
    if spread is None or spread > cfg["max_spread_rate"]:
        return FilterResult(passed=False, reason="spread too wide")

    trading_value = _get_float(metrics, "trading_value")
    if trading_value is None or trading_value < cfg["min_trading_value"]:
        return FilterResult(passed=False, reason="trading_value too low")

    return FilterResult(passed=True)