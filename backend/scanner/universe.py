"""Universe Filter — KOSPI/KOSDAQ 보통주 검증

Universe는 SAT3의 최상위 진입 조건이다.
KOSPI/KOSDAQ 보통주만 허용하며, ETF/ETN/ELW/REIT/SPAC/우선주/인버스/레버리지/UNKNOWN은 제외한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scanner.scanner_types import ExclusionReason

# 허용 시장
ALLOWED_MARKETS: frozenset[str] = frozenset({"KOSPI", "KOSDAQ"})

# 허용 상품 유형
ALLOWED_PRODUCT_TYPE: str = "COMMON_STOCK"

# 명시적 제외 상품 유형
EXCLUDED_PRODUCT_TYPES: frozenset[str] = frozenset({
    "ETF", "ETN", "ELW", "REIT", "SPAC",
    "PREFERRED_STOCK", "WARRANT",
    "INVERSE", "LEVERAGED",
})

# 상품 유형 → 제외 사유 매핑
PRODUCT_TYPE_TO_REASON: dict[str, ExclusionReason] = {
    "ETF": ExclusionReason.ETF_EXCLUDED,
    "ETN": ExclusionReason.ETN_EXCLUDED,
    "ELW": ExclusionReason.ELW_EXCLUDED,
    "REIT": ExclusionReason.REIT_EXCLUDED,
    "SPAC": ExclusionReason.SPAC_EXCLUDED,
    "PREFERRED_STOCK": ExclusionReason.PREFERRED_STOCK_EXCLUDED,
    "WARRANT": ExclusionReason.WARRANT_EXCLUDED,
    "INVERSE": ExclusionReason.INVERSE_EXCLUDED,
    "LEVERAGED": ExclusionReason.LEVERAGED_EXCLUDED,
}


@dataclass(frozen=True)
class UniverseCheckResult:
    """Universe 검증 결과"""
    included: bool
    excluded_reason: str | None
    metrics: dict[str, Any]


def check_universe(
    market: str | None,
    product_type: str | None,
    source: str | None,
    **extra_metrics: Any,
) -> UniverseCheckResult:
    """KOSPI/KOSDAQ 보통주 Universe 검증

    우선순위:
    1. KIS_SOURCE_INVALID — source 검증이 가장 우선
    2. NOT_KOSPI_KOSDAQ — 시장 확인
    3. 상품 유형별 제외 (ETF, ETN, ...)
    4. NOT_COMMON_STOCK — 보통주가 아닌 경우
    5. 통과

    Args:
        market: 시장 코드 ("KOSPI", "KOSDAQ", ...)
        product_type: 상품 유형 ("COMMON_STOCK", "ETF", ...)
        source: 데이터 출처 ("KIS_API" 또는 None)
        **extra_metrics: 추가 metric 정보

    Returns:
        UniverseCheckResult
    """
    metrics: dict[str, Any] = {
        "market": market,
        "product_type": product_type,
        "source": source,
        **extra_metrics,
    }

    # 1. source 검증 (최우선)
    if source is None or source.upper() != "KIS_API":
        return UniverseCheckResult(
            included=False,
            excluded_reason=ExclusionReason.KIS_SOURCE_INVALID.value,
            metrics=metrics,
        )

    # 2. 시장 확인
    if market is None or market.upper() not in ALLOWED_MARKETS:
        return UniverseCheckResult(
            included=False,
            excluded_reason=ExclusionReason.NOT_KOSPI_KOSDAQ.value,
            metrics=metrics,
        )

    # 3. 상품 유형별 제외
    if product_type is None:
        return UniverseCheckResult(
            included=False,
            excluded_reason=ExclusionReason.UNKNOWN_PRODUCT_TYPE.value,
            metrics=metrics,
        )

    pt_upper = product_type.upper()

    if pt_upper in EXCLUDED_PRODUCT_TYPES:
        reason = PRODUCT_TYPE_TO_REASON.get(pt_upper, ExclusionReason.NOT_COMMON_STOCK)
        return UniverseCheckResult(
            included=False,
            excluded_reason=reason.value,
            metrics=metrics,
        )

    # 4. UNKNOWN 상품 유형
    if pt_upper == "UNKNOWN":
        return UniverseCheckResult(
            included=False,
            excluded_reason=ExclusionReason.UNKNOWN_PRODUCT_TYPE.value,
            metrics=metrics,
        )

    # 5. 보통주 확인
    if pt_upper != ALLOWED_PRODUCT_TYPE:
        return UniverseCheckResult(
            included=False,
            excluded_reason=ExclusionReason.NOT_COMMON_STOCK.value,
            metrics=metrics,
        )

    # 6. 통과
    return UniverseCheckResult(
        included=True,
        excluded_reason=None,
        metrics=metrics,
    )