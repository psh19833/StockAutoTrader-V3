"""ScannerCandidate Model — 후보 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from scanner.scanner_types import ScannerType

ALLOWED_MARKETS = frozenset({"KOSPI", "KOSDAQ"})
ALLOWED_PRODUCT_TYPE: str = "COMMON_STOCK"
ALLOWED_SOURCE: str = "KIS_API"


@dataclass(frozen=True)
class ScannerCandidate:
    """SAT3 Scanner Candidate

    Scanner가 발굴한 단일 후보.
    정량 조건 기반 편입/탈락 근거를 포함한다.

    Attributes:
        symbol: 종목 코드
        symbol_name: 종목명 (선택)
        market: 시장 (KOSPI/KOSDAQ)
        product_type: 상품 유형 (COMMON_STOCK)
        scanner_type: 발굴한 Scanner Type
        discovered_at: 발굴 시각
        discovered_reason: 편입 사유 튜플
        metrics: 정량 메트릭
        source_endpoints: 데이터 출처 엔드포인트
        source: 데이터 출처 (KIS_API)
        scan_run_id: 스캔 실행 ID
        included: 후보 포함 여부
        excluded_reason: 제외 사유 (포함 시 None)
    """
    symbol: str
    market: Literal["KOSPI", "KOSDAQ"]
    product_type: Literal["COMMON_STOCK"]
    scanner_type: ScannerType
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    symbol_name: str | None = None
    discovered_reason: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    source_endpoints: tuple[str, ...] = ()
    source: str = "KIS_API"
    scan_run_id: str = ""
    included: bool = True
    excluded_reason: str | None = None