"""Scoring Configuration — 점수 가중치, Threshold, 시장 상태별 정책"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScoringConfig:
    """Quant 점수 설정"""
    # 공통 threshold
    pass_threshold: float = 50.0
    watch_threshold: float = 25.0

    # 점수 가중치 (향후 확장용)
    weights: dict[str, float] = field(default_factory=lambda: {
        "liquidity": 1.0,
        "spread": 1.0,
        "volume": 1.0,
        "momentum": 1.0,
        "trend": 1.0,
        "orderbook": 1.0,
        "volatility_safety": 1.0,
    })

    # Scanner Type별 threshold (기본값 기준 오버라이드)
    scanner_thresholds: dict[str, dict[str, float]] = field(default_factory=lambda: {
        "RAPID_SURGE": {
            "pass_threshold": 55.0,
            "watch_threshold": 30.0,
        },
        "LIQUIDITY_MOMENTUM": {
            "pass_threshold": 50.0,
            "watch_threshold": 25.0,
        },
        "BREAKOUT": {
            "pass_threshold": 55.0,
            "watch_threshold": 28.0,
        },
        "PULLBACK_REBOUND": {
            "pass_threshold": 45.0,
            "watch_threshold": 22.0,
        },
    })

    # Market Regime별 정책
    regime_policies: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "BULL": {
            "adjustment": 5.0,
            "allow_new_buy": True,
            "pass_threshold_bonus": -5.0,  # threshold 완화 (-5 → 더 쉽게 PASS)
        },
        "NEUTRAL": {
            "adjustment": 0.0,
            "allow_new_buy": True,
            "pass_threshold_bonus": None,
        },
        "BEAR": {
            "adjustment": -15.0,
            "allow_new_buy": False,
            "pass_threshold_bonus": None,
        },
        "UNKNOWN": {
            "adjustment": -30.0,
            "allow_new_buy": False,
            "pass_threshold_bonus": None,
        },
    })


# 전역 기본 설정
DEFAULT_SCORING_CONFIG = ScoringConfig()


def get_scoring_config(overrides: dict[str, Any] | None = None) -> ScoringConfig:
    """설정 오버라이드 적용"""
    if not overrides:
        return DEFAULT_SCORING_CONFIG

    cfg = DEFAULT_SCORING_CONFIG
    pass_threshold = overrides.get("pass_threshold", cfg.pass_threshold)
    watch_threshold = overrides.get("watch_threshold", cfg.watch_threshold)
    weights = dict(cfg.weights)
    weights.update(overrides.get("weights", {}))
    scanner_thresholds = dict(cfg.scanner_thresholds)
    scanner_thresholds.update(
        overrides.get("scanner_thresholds", {})
    )
    regime_policies = dict(cfg.regime_policies)
    regime_policies.update(
        overrides.get("regime_policies", {})
    )
    return ScoringConfig(
        pass_threshold=pass_threshold,
        watch_threshold=watch_threshold,
        weights=weights,
        scanner_thresholds=scanner_thresholds,
        regime_policies=regime_policies,
    )


def get_regime_adjustment(regime: str) -> float:
    """시장 상태별 기본 보정값"""
    policy = DEFAULT_SCORING_CONFIG.regime_policies.get(regime)
    if policy is None:
        return -30.0  # 알 수 없는 시장 상태 → 보수적 차단
    return float(policy["adjustment"])


def get_scanner_specific_config(scanner_type: str) -> dict[str, float]:
    """Scanner Type별 threshold 설정"""
    return dict(
        DEFAULT_SCORING_CONFIG.scanner_thresholds.get(scanner_type, {})
    )