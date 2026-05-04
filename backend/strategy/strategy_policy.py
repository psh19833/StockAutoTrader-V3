"""Strategy Policy — Market Regime별 전략 활성 정책"""
from __future__ import annotations

from dataclasses import dataclass

from strategy.strategy_types import StrategyType


@dataclass(frozen=True)
class StrategyPolicy:
    """Market Regime별 전략 활성 정책"""
    rapid_surge_enabled: bool = True
    liquidity_momentum_enabled: bool = True
    breakout_enabled: bool = True
    pullback_enabled: bool = True
    rapid_surge_min_confidence: float = 0.6
    breakout_min_confidence: float = 0.7

    def is_enabled(self, strategy_type: StrategyType) -> bool:
        mapping = {
            StrategyType.RAPID_SURGE_SCALPING: self.rapid_surge_enabled,
            StrategyType.LIQUIDITY_MOMENTUM_FOLLOW: self.liquidity_momentum_enabled,
            StrategyType.BREAKOUT_FOLLOW: self.breakout_enabled,
            StrategyType.PULLBACK_REBOUND: self.pullback_enabled,
            StrategyType.FAST_EXIT: True,  # always enabled
        }
        return mapping.get(strategy_type, False)

    def min_confidence(self, strategy_type: StrategyType) -> float:
        mapping = {
            StrategyType.RAPID_SURGE_SCALPING: self.rapid_surge_min_confidence,
            StrategyType.BREAKOUT_FOLLOW: self.breakout_min_confidence,
        }
        return mapping.get(strategy_type, 0.5)


# Default policies per market regime
BULL_POLICY = StrategyPolicy(
    rapid_surge_enabled=True,
    liquidity_momentum_enabled=True,
    breakout_enabled=True,
    pullback_enabled=True,
    rapid_surge_min_confidence=0.6,
    breakout_min_confidence=0.7,
)

NEUTRAL_POLICY = StrategyPolicy(
    rapid_surge_enabled=True,
    liquidity_momentum_enabled=True,
    breakout_enabled=True,
    pullback_enabled=True,
    rapid_surge_min_confidence=0.75,
    breakout_min_confidence=0.80,
)

BEAR_POLICY = StrategyPolicy(
    rapid_surge_enabled=False,
    liquidity_momentum_enabled=False,
    breakout_enabled=False,
    pullback_enabled=False,
)

UNKNOWN_POLICY = StrategyPolicy(
    rapid_surge_enabled=False,
    liquidity_momentum_enabled=False,
    breakout_enabled=False,
    pullback_enabled=False,
)


def get_policy_for_regime(regime: str) -> StrategyPolicy:
    """Market Regime에 맞는 전략 정책 반환"""
    policies = {
        "BULL": BULL_POLICY,
        "NEUTRAL": NEUTRAL_POLICY,
        "BEAR": BEAR_POLICY,
        "UNKNOWN": UNKNOWN_POLICY,
    }
    return policies.get(regime, UNKNOWN_POLICY)
