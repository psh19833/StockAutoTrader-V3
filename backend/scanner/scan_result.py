"""ScanRunResult — Scanner 실행 결과 모델"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate


@dataclass(frozen=True)
class ScanRunResult:
    """Scanner 실행 결과

    단일 Scanner Type의 한 번의 스캔 실행 결과.
    수집/제외/포함 카운트와 후보 목록을 포함한다.

    Attributes:
        scan_run_id: 스캔 실행 ID
        scanner_type: Scanner Type
        started_at: 스캔 시작 시각
        completed_at: 스캔 완료 시각
        market_regime: 스캔 당시 시장 상태
        collected_count: 수집된 종목 수
        excluded_count: 제외된 종목 수
        included_count: 포함된 후보 수
        candidates: 후보 목록
        source_endpoints: 사용된 엔드포인트
        data_quality_warnings: 데이터 품질 경고
    """
    scan_run_id: str
    scanner_type: ScannerType
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    market_regime: str = ""
    collected_count: int = 0
    excluded_count: int = 0
    included_count: int = 0
    candidates: tuple[ScannerCandidate, ...] = ()
    source_endpoints: tuple[str, ...] = ()
    data_quality_warnings: tuple[str, ...] = ()