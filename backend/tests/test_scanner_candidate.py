"""Tests for ScannerCandidate model"""
from __future__ import annotations

from datetime import datetime

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate


class TestScannerCandidate:
    """ScannerCandidate model tests"""

    def test_minimal_candidate_creation(self):
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=("high_surge_rate", "volume_burst"),
            metrics={"change_rate": 3.5, "volume_ratio": 2.0},
            source_endpoints=("kis/quote",),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert candidate.symbol == "005930"
        assert candidate.market == "KOSPI"
        assert candidate.product_type == "COMMON_STOCK"
        assert candidate.scanner_type == ScannerType.RAPID_SURGE
        assert candidate.included is True
        assert candidate.excluded_reason is None

    def test_candidate_with_name(self):
        candidate = ScannerCandidate(
            symbol="005930",
            symbol_name="삼성전자",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.LIQUIDITY_MOMENTUM,
            discovered_reason=("high_trading_value",),
            metrics={"trading_value_rank": 5},
            source_endpoints=("kis/rank",),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert candidate.symbol_name == "삼성전자"

    def test_candidate_without_name(self):
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert candidate.symbol_name is None

    def test_excluded_candidate(self):
        candidate = ScannerCandidate(
            symbol="069500",
            market="KOSPI",
            product_type="ETF",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=False,
            excluded_reason="ETF_EXCLUDED",
        )
        assert candidate.included is False
        assert candidate.excluded_reason == "ETF_EXCLUDED"

    def test_candidate_is_frozen(self):
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        import pytest
        with pytest.raises(AttributeError):
            candidate.symbol = "000660"  # frozen

    def test_discovered_at_is_datetime(self):
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert isinstance(candidate.discovered_at, datetime)

    def test_has_no_order_fields(self):
        """ScannerCandidate는 주문 관련 필드를 가지지 않음"""
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert not hasattr(candidate, "buy_signal")
        assert not hasattr(candidate, "sell_signal")
        assert not hasattr(candidate, "order_intent")
        assert not hasattr(candidate, "quantity")
        assert not hasattr(candidate, "stop_loss")
        assert not hasattr(candidate, "take_profit")
        assert not hasattr(candidate, "approve_order")

    def test_discovered_reason_is_tuple_of_strings(self):
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=("high_surge_rate", "volume_burst"),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert isinstance(candidate.discovered_reason, tuple)
        assert all(isinstance(r, str) for r in candidate.discovered_reason)

    def test_all_4_scanner_types_work(self):
        """모든 ScannerType으로 candidate 생성 가능"""
        for st in ScannerType:
            candidate = ScannerCandidate(
                symbol="005930",
                market="KOSPI",
                product_type="COMMON_STOCK",
                scanner_type=st,
                discovered_reason=(),
                metrics={},
                source_endpoints=(),
                source="KIS_API",
                scan_run_id="scan_001",
                included=True,
            )
            assert candidate.scanner_type == st

    def test_source_is_kis_api(self):
        candidate = ScannerCandidate(
            symbol="005930",
            market="KOSPI",
            product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(),
            metrics={},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        assert candidate.source == "KIS_API"

    def test_included_tracks_true_false(self):
        """included가 True/False 모두 정상 동작"""
        for included in [True, False]:
            candidate = ScannerCandidate(
                symbol="005930",
                market="KOSPI",
                product_type="COMMON_STOCK",
                scanner_type=ScannerType.RAPID_SURGE,
                discovered_reason=(),
                metrics={},
                source_endpoints=(),
                source="KIS_API",
                scan_run_id="scan_001",
                included=included,
            )
            assert candidate.included is included