"""Strategy Type enum — SAT3 strategy types"""
from __future__ import annotations

from enum import Enum


class StrategyType(str, Enum):
    """SAT3 Strategy Types

    5 types: 4 entry strategies + 1 exit strategy.
    StrategySignal is NOT an order — it's an intent.
    """
    RAPID_SURGE_SCALPING = "RAPID_SURGE_SCALPING"
    LIQUIDITY_MOMENTUM_FOLLOW = "LIQUIDITY_MOMENTUM_FOLLOW"
    BREAKOUT_FOLLOW = "BREAKOUT_FOLLOW"
    PULLBACK_REBOUND = "PULLBACK_REBOUND"
    FAST_EXIT = "FAST_EXIT"
