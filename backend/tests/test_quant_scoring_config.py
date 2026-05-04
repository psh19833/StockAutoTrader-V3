"""Tests for Scoring Configuration"""
from __future__ import annotations

from quant.scoring_config import (
    ScoringConfig,
    DEFAULT_SCORING_CONFIG,
    get_scoring_config,
    get_regime_adjustment,
    get_scanner_specific_config,
)


class TestScoringConfig:
    """ScoringConfig 설정 테스트"""

    def test_default_config_exists(self):
        assert DEFAULT_SCORING_CONFIG is not None
        assert isinstance(DEFAULT_SCORING_CONFIG, ScoringConfig)

    def test_default_pass_threshold(self):
        assert DEFAULT_SCORING_CONFIG.pass_threshold >= DEFAULT_SCORING_CONFIG.watch_threshold

    def test_default_has_scanner_configs(self):
        from scanner.scanner_types import ScannerType
        for st in ScannerType:
            assert st.value in DEFAULT_SCORING_CONFIG.scanner_thresholds

    def test_default_has_regime_policies(self):
        regimes = ["BULL", "NEUTRAL", "BEAR", "UNKNOWN"]
        for regime in regimes:
            assert regime in DEFAULT_SCORING_CONFIG.regime_policies

    def test_bull_regime_policy(self):
        policy = DEFAULT_SCORING_CONFIG.regime_policies["BULL"]
        assert policy["adjustment"] >= 0  # BULL은 양수 보정
        assert policy["pass_threshold_bonus"] is not None

    def test_neutral_regime_policy(self):
        policy = DEFAULT_SCORING_CONFIG.regime_policies["NEUTRAL"]
        assert policy["adjustment"] == 0.0
        assert policy["pass_threshold_bonus"] is None

    def test_bear_regime_policy(self):
        policy = DEFAULT_SCORING_CONFIG.regime_policies["BEAR"]
        assert policy["adjustment"] < 0  # BEAR은 음수 보정
        assert policy["allow_new_buy"] is False

    def test_unknown_regime_policy(self):
        policy = DEFAULT_SCORING_CONFIG.regime_policies["UNKNOWN"]
        assert policy["adjustment"] < 0
        assert policy["allow_new_buy"] is False

    def test_get_scoring_config_default(self):
        config = get_scoring_config({})
        assert config.pass_threshold == DEFAULT_SCORING_CONFIG.pass_threshold

    def test_get_scoring_config_override(self):
        custom = {"pass_threshold": 70.0, "watch_threshold": 40.0}
        config = get_scoring_config(custom)
        assert config.pass_threshold == 70.0
        assert config.watch_threshold == 40.0

    def test_get_regime_adjustment_bull(self):
        adj = get_regime_adjustment("BULL")
        assert isinstance(adj, float)
        assert adj >= 0

    def test_get_regime_adjustment_neutral(self):
        adj = get_regime_adjustment("NEUTRAL")
        assert adj == 0.0

    def test_get_regime_adjustment_bear(self):
        adj = get_regime_adjustment("BEAR")
        assert adj < 0

    def test_get_regime_adjustment_unknown(self):
        adj = get_regime_adjustment("UNKNOWN")
        assert adj < 0

    def test_get_regime_adjustment_invalid(self):
        adj = get_regime_adjustment("INVALID_REGIME")
        assert adj == -30.0  # 보수적 fallback

    def test_scanner_specific_config_rapid_surge(self):
        cfg = get_scanner_specific_config("RAPID_SURGE")
        assert cfg is not None
        assert "pass_threshold" in cfg

    def test_scanner_specific_config_liquidity_momentum(self):
        cfg = get_scanner_specific_config("LIQUIDITY_MOMENTUM")
        assert cfg is not None

    def test_scanner_specific_config_breakout(self):
        cfg = get_scanner_specific_config("BREAKOUT")
        assert cfg is not None

    def test_scanner_specific_config_pullback_rebound(self):
        cfg = get_scanner_specific_config("PULLBACK_REBOUND")
        assert cfg is not None

    def test_scanner_specific_config_missing(self):
        cfg = get_scanner_specific_config("UNKNOWN_SCANNER")
        assert cfg == {}