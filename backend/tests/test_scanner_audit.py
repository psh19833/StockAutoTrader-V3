"""Tests for Scanner Audit — AuditEvent 변환"""
from __future__ import annotations

from datetime import datetime

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate
from scanner.scan_result import ScanRunResult
from scanner.scanner_audit import (
    build_scan_started_event,
    build_scan_completed_event,
    build_candidate_discovered_event,
    build_candidate_excluded_event,
)


class TestScannerAudit:
    """Scanner AuditEvent 변환 테스트"""

    def test_scan_started_event(self):
        event = build_scan_started_event(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="BULL",
        )
        assert event.event_type == "SCAN_STARTED"
        assert event.payload["scan_run_id"] == "scan_001"
        assert event.payload["scanner_type"] == "RAPID_SURGE"
        assert event.payload["market_regime"] == "BULL"
        assert event.source == "scanner"

    def test_scan_completed_event(self):
        candidates = [
            ScannerCandidate(
                symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
                scanner_type=ScannerType.RAPID_SURGE,
                discovered_reason=(), metrics={},
                source_endpoints=(), source="KIS_API",
                scan_run_id="scan_001", included=True,
            )
        ]
        result = ScanRunResult(
            scan_run_id="scan_001",
            scanner_type=ScannerType.RAPID_SURGE,
            market_regime="BULL",
            collected_count=10,
            excluded_count=9,
            included_count=1,
            candidates=tuple(candidates),
        )
        event = build_scan_completed_event(result)
        assert event.event_type == "SCAN_COMPLETED"
        assert event.payload["scanner_type"] == "RAPID_SURGE"
        assert event.payload["collected_count"] == 10
        assert event.payload["excluded_count"] == 9
        assert event.payload["included_count"] == 1
        assert event.payload["candidate_count"] == 1

    def test_candidate_discovered_event(self):
        candidate = ScannerCandidate(
            symbol="005930", symbol_name="삼성전자",
            market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=("surge_rate_high", "volume_burst"),
            metrics={"change_rate": 3.5},
            source_endpoints=("kis/quote",),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        event = build_candidate_discovered_event(candidate)
        assert event.event_type == "CANDIDATE_DISCOVERED"
        assert event.symbol == "005930"
        assert event.payload["symbol_name"] == "삼성전자"
        assert event.payload["scanner_type"] == "RAPID_SURGE"
        assert event.payload["discovered_reason"] == ("surge_rate_high", "volume_burst")
        assert event.payload["change_rate"] == 3.5
        assert event.source == "scanner"

    def test_candidate_excluded_event(self):
        candidate = ScannerCandidate(
            symbol="069500", market="KOSPI", product_type="ETF",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(), metrics={},
            source_endpoints=(), source="KIS_API",
            scan_run_id="scan_001",
            included=False,
            excluded_reason="ETF_EXCLUDED",
        )
        event = build_candidate_excluded_event(candidate)
        assert event.event_type == "CANDIDATE_EXCLUDED"
        assert event.symbol == "069500"
        assert event.payload["scanner_type"] == "RAPID_SURGE"
        assert event.payload["excluded_reason"] == "ETF_EXCLUDED"
        assert event.source == "scanner"

    def test_candidate_discovered_serializable(self):
        """AuditEvent payload는 JSON 직렬화 가능해야 함"""
        candidate = ScannerCandidate(
            symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=("reason_a",),
            metrics={"val": 1.5},
            source_endpoints=(),
            source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        event = build_candidate_discovered_event(candidate)

        import json
        # 모든 payload 값은 JSON 직렬화 가능해야 함
        serialized = json.dumps({
            "event_type": event.event_type,
            "symbol": event.symbol,
            "payload": event.payload,
        })
        assert isinstance(serialized, str)
        assert '"reason_a"' in serialized
        assert "CANDIDATE_DISCOVERED" in serialized

    def test_no_secret_leak_in_event(self):
        """AuditEvent payload에 secret/token/account 노출 금지"""
        candidate = ScannerCandidate(
            symbol="005930", market="KOSPI", product_type="COMMON_STOCK",
            scanner_type=ScannerType.RAPID_SURGE,
            discovered_reason=(), metrics={},
            source_endpoints=(), source="KIS_API",
            scan_run_id="scan_001",
            included=True,
        )
        event = build_candidate_discovered_event(candidate)
        event_str = str(event)
        forbidden = ["api_key", "api_secret", "access_token", "account_no",
                     "chat_id", "token", "secret", "password"]
        for term in forbidden:
            assert term not in event_str.lower(), f"Secret leak: {term}"