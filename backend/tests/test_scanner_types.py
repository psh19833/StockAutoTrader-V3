"""Tests for ScannerType and ExclusionReason enums"""
from __future__ import annotations

from scanner.scanner_types import ScannerType, ExclusionReason


class TestScannerType:
    """ScannerType enum tests"""

    def test_has_4_types(self):
        assert len(ScannerType) == 4

    def test_has_rapid_surge(self):
        assert ScannerType.RAPID_SURGE == "RAPID_SURGE"

    def test_has_liquidity_momentum(self):
        assert ScannerType.LIQUIDITY_MOMENTUM == "LIQUIDITY_MOMENTUM"

    def test_has_breakout(self):
        assert ScannerType.BREAKOUT == "BREAKOUT"

    def test_has_pullback_rebound(self):
        assert ScannerType.PULLBACK_REBOUND == "PULLBACK_REBOUND"

    def test_all_values_are_unique(self):
        values = [e.value for e in ScannerType]
        assert len(values) == len(set(values))


class TestExclusionReason:
    """ExclusionReason enum tests"""

    def test_has_universe_reasons(self):
        assert ExclusionReason.NOT_KOSPI_KOSDAQ == "NOT_KOSPI_KOSDAQ"
        assert ExclusionReason.NOT_COMMON_STOCK == "NOT_COMMON_STOCK"

    def test_has_product_type_reasons(self):
        assert ExclusionReason.ETF_EXCLUDED == "ETF_EXCLUDED"
        assert ExclusionReason.ETN_EXCLUDED == "ETN_EXCLUDED"
        assert ExclusionReason.ELW_EXCLUDED == "ELW_EXCLUDED"
        assert ExclusionReason.REIT_EXCLUDED == "REIT_EXCLUDED"
        assert ExclusionReason.SPAC_EXCLUDED == "SPAC_EXCLUDED"
        assert ExclusionReason.PREFERRED_STOCK_EXCLUDED == "PREFERRED_STOCK_EXCLUDED"
        assert ExclusionReason.WARRANT_EXCLUDED == "WARRANT_EXCLUDED"
        assert ExclusionReason.INVERSE_EXCLUDED == "INVERSE_EXCLUDED"
        assert ExclusionReason.LEVERAGED_EXCLUDED == "LEVERAGED_EXCLUDED"
        assert ExclusionReason.UNKNOWN_PRODUCT_TYPE == "UNKNOWN_PRODUCT_TYPE"

    def test_has_common_filter_reasons(self):
        assert ExclusionReason.PRICE_TOO_HIGH == "PRICE_TOO_HIGH"
        assert ExclusionReason.PRICE_TOO_LOW == "PRICE_TOO_LOW"
        assert ExclusionReason.TRADING_VALUE_TOO_LOW == "TRADING_VALUE_TOO_LOW"
        assert ExclusionReason.VOLUME_TOO_LOW == "VOLUME_TOO_LOW"
        assert ExclusionReason.SPREAD_TOO_WIDE == "SPREAD_TOO_WIDE"
        assert ExclusionReason.TRADING_HALTED == "TRADING_HALTED"
        assert ExclusionReason.MANAGEMENT_ISSUE == "MANAGEMENT_ISSUE"
        assert ExclusionReason.INVESTMENT_WARNING == "INVESTMENT_WARNING"
        assert ExclusionReason.VI_ACTIVE == "VI_ACTIVE"
        assert ExclusionReason.KIS_SOURCE_INVALID == "KIS_SOURCE_INVALID"
        assert ExclusionReason.DATA_UNAVAILABLE == "DATA_UNAVAILABLE"

    def test_has_scanner_reasons(self):
        assert ExclusionReason.SCANNER_CONDITION_NOT_MET == "SCANNER_CONDITION_NOT_MET"
        assert ExclusionReason.MARKET_REGIME_BLOCKED == "MARKET_REGIME_BLOCKED"

    def test_total_exclusion_reasons(self):
        # 23 base + 2 scanner-specific = 25
        assert len(ExclusionReason) == 25

    def test_all_values_are_unique(self):
        values = [e.value for e in ExclusionReason]
        assert len(values) == len(set(values))

    def test_no_order_related_terms(self):
        """Scanner exclusion reasons must not contain buy/sell/order terms"""
        forbidden = ["BUY", "SELL", "ORDER", "SIGNAL", "STOP_LOSS", "TAKE_PROFIT"]
        values_str = " ".join(e.value for e in ExclusionReason)
        for term in forbidden:
            assert term not in values_str, f"ExclusionReason contains forbidden term: {term}"