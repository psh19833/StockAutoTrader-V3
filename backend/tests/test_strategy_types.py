"""Tests for Strategy Type enum"""
from __future__ import annotations

from strategy.strategy_types import StrategyType


class TestStrategyType:
    def test_has_5_types(self):
        assert len(StrategyType) == 5

    def test_has_rapid_surge_scalping(self):
        assert StrategyType.RAPID_SURGE_SCALPING.value == "RAPID_SURGE_SCALPING"

    def test_has_liquidity_momentum_follow(self):
        assert StrategyType.LIQUIDITY_MOMENTUM_FOLLOW.value == "LIQUIDITY_MOMENTUM_FOLLOW"

    def test_has_breakout_follow(self):
        assert StrategyType.BREAKOUT_FOLLOW.value == "BREAKOUT_FOLLOW"

    def test_has_pullback_rebound(self):
        assert StrategyType.PULLBACK_REBOUND.value == "PULLBACK_REBOUND"

    def test_has_fast_exit(self):
        assert StrategyType.FAST_EXIT.value == "FAST_EXIT"

    def test_all_values_unique(self):
        values = [s.value for s in StrategyType]
        assert len(values) == len(set(values))

    def test_str_enum(self):
        assert isinstance(StrategyType.RAPID_SURGE_SCALPING, str)
