"""Tests for ScanRunResult model"""
from __future__ import annotations

from datetime import datetime

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate
from scanner.scan_result import ScanRunResult


class TestScanRunResult:
    """ScanRunResult model tests"""

    def test_minimal_scan_result(self):
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="NEUTRAL",
        )
        assert result.scan_run_id == "scan_001"
        assert result.scanner_type == ScannerType.RAPID_SURGE
        assert result.market_regime == "NEUTRAL"
        assert result.collected_count == 0
        assert result.excluded_count == 0
        assert result.included_count == 0
        assert result.candidates == ()

    def test_scan_result_with_candidates(self):
        c1 = ScannerCandidate(
            symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=("surge",), metrics={},
            source_endpoints=(), source="KIS_API",
            scan_run_id="scan_001", included=True,
        )
        c2 = ScannerCandidate(
            symbol="000660", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=("surge",), metrics={},
            source_endpoints=(), source="KIS_API",
            scan_run_id="scan_001", included=False,
            excluded_reason="PRICE_TOO_HIGH",
        )
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="BULL",
            collected_count=10,
            excluded_count=8,
            included_count=2,
            candidates=(c1, c2),
            source_endpoints=("kis/quote",),
        )
        assert result.collected_count == 10
        assert result.excluded_count == 8
        assert result.included_count == 2
        assert len(result.candidates) == 2
        assert result.source_endpoints == ("kis/quote",)

    def test_started_at_and_completed_at(self):
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="NEUTRAL",
        )
        assert isinstance(result.started_at, datetime)
        assert isinstance(result.completed_at, datetime)
        assert result.completed_at >= result.started_at

    def test_data_quality_warnings(self):
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="NEUTRAL",
            data_quality_warnings=("low_trading_value_count",),
        )
        assert result.data_quality_warnings == ("low_trading_value_count",)

    def test_is_excluded_count_auto_tracked(self):
        """excluded_count와 included_count는 수동 설정"""
        c1 = ScannerCandidate(
            symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(), metrics={},
            source_endpoints=(), source="KIS_API",
            scan_run_id="scan_001", included=True,
        )
        c2 = ScannerCandidate(
            symbol="069500", market="KOSPI", product_type="ETF",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(), metrics={},
            source_endpoints=(), source="KIS_API",
            scan_run_id="scan_001", included=False,
            excluded_reason="ETF_EXCLUDED",
        )
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="NEUTRAL",
            collected_count=2,
            excluded_count=1,
            included_count=1,
            candidates=(c1, c2),
        )
        assert result.collected_count == 2
        assert result.excluded_count == 1
        assert result.included_count == 1

    def test_no_order_fields(self):
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="NEUTRAL",
        )
        assert not hasattr(result, "buy_signal")
        assert not hasattr(result, "order_intent")
        assert not hasattr(result, "sell_signal")