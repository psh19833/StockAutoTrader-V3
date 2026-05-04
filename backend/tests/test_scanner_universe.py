"""Tests for Universe Filter (KOSPI/KOSDAQ common stock validation)"""
from __future__ import annotations

from scanner.scanner_types import ExclusionReason
from scanner.universe import check_universe


class TestUniverseCheck:
    """Universe filter tests — KOSPI/KOSDAQ 보통주 확인"""

    def test_kospi_common_stock_passes(self):
        result = check_universe(
            market="KOSPI", product_type="COMMON_STOCK", source="KIS_API"
        )
        assert result.included is True
        assert result.excluded_reason is None

    def test_kosdaq_common_stock_passes(self):
        result = check_universe(
            market="KOSDAQ", product_type="COMMON_STOCK", source="KIS_API"
        )
        assert result.included is True
        assert result.excluded_reason is None

    def test_not_kospi_kosdaq_excluded(self):
        result = check_universe(
            market="NYSE", product_type="COMMON_STOCK", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.NOT_KOSPI_KOSDAQ.value

    def test_unknown_market_excluded(self):
        result = check_universe(
            market="UNKNOWN", product_type="COMMON_STOCK", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.NOT_KOSPI_KOSDAQ.value

    def test_etf_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="ETF", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.ETF_EXCLUDED.value

    def test_etn_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="ETN", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.ETN_EXCLUDED.value

    def test_elw_excluded(self):
        result = check_universe(
            market="KOSDAQ", product_type="ELW", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.ELW_EXCLUDED.value

    def test_reit_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="REIT", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.REIT_EXCLUDED.value

    def test_spac_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="SPAC", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.SPAC_EXCLUDED.value

    def test_preferred_stock_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="PREFERRED_STOCK", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.PREFERRED_STOCK_EXCLUDED.value

    def test_warrant_excluded(self):
        result = check_universe(
            market="KOSDAQ", product_type="WARRANT", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.WARRANT_EXCLUDED.value

    def test_inverse_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="INVERSE", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.INVERSE_EXCLUDED.value

    def test_leveraged_excluded(self):
        result = check_universe(
            market="KOSDAQ", product_type="LEVERAGED", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.LEVERAGED_EXCLUDED.value

    def test_unknown_product_type_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="UNKNOWN", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.UNKNOWN_PRODUCT_TYPE.value

    def test_none_product_type_excluded(self):
        result = check_universe(
            market="KOSPI", product_type=None, source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.UNKNOWN_PRODUCT_TYPE.value

    def test_not_common_stock_excluded(self):
        """COMMON_STOCK이 아니면 NOT_COMMON_STOCK"""
        result = check_universe(
            market="KOSPI", product_type="MEMBERSHIP", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.NOT_COMMON_STOCK.value

    def test_kis_source_invalid_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="COMMON_STOCK", source="CRAWLER"
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.KIS_SOURCE_INVALID.value

    def test_none_source_invalid_excluded(self):
        result = check_universe(
            market="KOSPI", product_type="COMMON_STOCK", source=None
        )
        assert result.included is False
        assert result.excluded_reason == ExclusionReason.KIS_SOURCE_INVALID.value

    def test_exclusion_priority_market_before_product(self):
        """NOT_KOSPI_KOSDAQ이 ETF_EXCLUDED보다 우선"""
        result = check_universe(
            market="NYSE", product_type="ETF", source="KIS_API"
        )
        assert result.excluded_reason == ExclusionReason.NOT_KOSPI_KOSDAQ.value

    def test_exclusion_priority_kis_before_all(self):
        """KIS_SOURCE_INVALID가 universe/상품 확인보다 우선"""
        result = check_universe(
            market="KOSPI", product_type="COMMON_STOCK", source=None
        )
        assert result.excluded_reason == ExclusionReason.KIS_SOURCE_INVALID.value

    def test_scanner_makes_no_order_objects(self):
        """Scanner는 OrderIntent, BuySignal, SellSignal을 만들지 않음"""
        result = check_universe(
            market="KOSPI", product_type="COMMON_STOCK", source="KIS_API"
        )
        # result는 dataclass — 주문 관련 필드 없음
        assert not hasattr(result, "order")
        assert not hasattr(result, "buy_signal")
        assert not hasattr(result, "order_intent")
        assert not hasattr(result, "sell_signal")

    def test_excluded_items_have_detailed_reason(self):
        """제외된 항목은 구체적인 사유를 남김"""
        result = check_universe(
            market="KOSPI", product_type="ETF", source="KIS_API"
        )
        assert result.included is False
        assert result.excluded_reason is not None
        assert result.excluded_reason != ""

    def test_included_items_have_metrics(self):
        """포함된 항목은 metric 정보를 함께 반환"""
        result = check_universe(
            market="KOSPI", product_type="COMMON_STOCK", source="KIS_API"
        )
        assert result.included is True
        assert isinstance(result.metrics, dict)
        assert result.metrics["market"] == "KOSPI"
        assert result.metrics["product_type"] == "COMMON_STOCK"