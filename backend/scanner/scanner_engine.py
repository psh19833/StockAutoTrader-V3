"""Scanner Engine — 정량 조건 기반 후보 발굴 오케스트레이션

Pipeline:
  1. stock_data → universe check (KOSPI/KOSDAQ 보통주)
  2. universe passed → common filters (가격, 거래대금, 거래량 등)
  3. common passed → scanner-specific filter (RAPID_SURGE, LIQUIDITY_MOMENTUM 등)
  4. 모든 단계 통과 → ScannerCandidate(included=True)
  5. 어느 단계든 실패 → ScannerCandidate(included=False, excluded_reason=...)
  6. 전체 결과 → ScanRunResult

Scanner는 매수/매도 신호를 만들지 않는다.
Scanner는 주문 수량, 손절가, 익절가를 계산하지 않는다.

핵심 안전 원칙:
  - Scanner에서 제외된 후보(excluded)는 다시 Quant PASS될 수 없다.
  - market/product_type은 원본 값을 보존하며 임의로 KOSPI/COMMON_STOCK으로 덮어쓰지 않는다.
  - source_endpoints는 후보별로 분리되어 다른 종목의 엔드포인트가 섞이지 않는다.
  - run_scanner의 market_regime 인자는 metrics["market_regime"]으로 명시 주입된다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from scanner.scanner_types import ScannerType, ExclusionReason
from scanner.candidate import ScannerCandidate
from scanner.scan_result import ScanRunResult
from scanner.universe import check_universe
from scanner.filters import (
    check_common_filters,
    check_rapid_surge,
    check_liquidity_momentum,
    check_breakout,
    check_pullback_rebound,
)

# Scanner Type → check function mapping
_SCANNER_CHECK_MAP = {
    ScannerType.RAPID_SURGE: check_rapid_surge,
    ScannerType.LIQUIDITY_MOMENTUM: check_liquidity_momentum,
    ScannerType.BREAKOUT: check_breakout,
    ScannerType.PULLBACK_REBOUND: check_pullback_rebound,
}


def run_scanner(
    stocks: list[dict[str, Any]],
    scanner_type: ScannerType,
    market_regime: str = "UNKNOWN",
    config: dict[str, Any] | None = None,
    scan_run_id: str | None = None,
) -> ScanRunResult:
    """단일 Scanner Type 실행

    Pipeline: universe → common filters → scanner filter

    Args:
        stocks: 종목별 metric dicts (symbol, market, product_type, source + metrics)
        scanner_type: 실행할 Scanner Type
        market_regime: 현재 시장 상태 ("BULL", "NEUTRAL", "BEAR", "UNKNOWN")
        config: Scanner 설정 오버라이드
        scan_run_id: 스캔 실행 ID (없으면 자동 생성)

    Returns:
        ScanRunResult (포함/제외된 후보 목록)
    """
    started_at = datetime.now(timezone.utc)
    scan_id = scan_run_id or f"scan_{uuid.uuid4().hex[:12]}"
    candidates: list[ScannerCandidate] = []
    scanner_check = _SCANNER_CHECK_MAP[scanner_type]
    endpoints: set[str] = set()

    for stock in stocks:
        symbol = str(stock.get("symbol", ""))
        symbol_name = stock.get("symbol_name")
        market = stock.get("market")
        product_type = stock.get("product_type")
        source = stock.get("source", "KIS_API")
        # STEP 2: run_scanner의 market_regime 인자를 metrics에 주입
        # stock에 이미 market_regime이 있어도 run_scanner 인자를 우선
        metrics = {k: v for k, v in stock.items()
                   if k not in ("symbol", "symbol_name", "market",
                                "product_type", "source")}
        metrics["market_regime"] = market_regime

        reason: str | None = None
        included = False
        discovered_reason: list[str] = []

        # Phase 1: Universe Check
        universe_result = check_universe(
            market=market,
            product_type=product_type,
            source=source,
            **metrics,
        )
        if not universe_result.included:
            reason = universe_result.excluded_reason
        else:
            # Phase 2: Common Filters
            common_result = check_common_filters(metrics)
            if not common_result.included:
                reason = common_result.excluded_reason
            else:
                # Phase 3: Scanner-specific Filter
                scanner_result = scanner_check(metrics, config)
                if scanner_result.passed:
                    included = True
                    reason = None
                    discovered_reason = [f"{scanner_type.value}:conditions_met"]
                else:
                    reason = scanner_result.reason if scanner_result.reason else ExclusionReason.SCANNER_CONDITION_NOT_MET.value

        # STEP 10: 후보별 source_endpoints — stock 자체의 것만 사용
        stock_endpoints = stock.get("source_endpoints", ())
        if isinstance(stock_endpoints, (list, tuple, set)):
            candidate_endpoints = tuple(stock_endpoints)
        else:
            candidate_endpoints = ()

        # Aggregate 전체 endpoints set (for scan result)
        if candidate_endpoints:
            endpoints.update(candidate_endpoints)

        # STEP 3: market/product_type 원본 보존
        # scanner_engine이 임의로 KOSPI/COMMON_STOCK으로 덮어쓰지 않음
        display_market = market or "UNKNOWN"
        display_product = product_type or "UNKNOWN"

        candidates.append(ScannerCandidate(
            symbol=symbol,
            market=display_market if display_market in ("KOSPI", "KOSDAQ", "UNKNOWN") else display_market,
            product_type=display_product,
            scanner_type=scanner_type,
            symbol_name=symbol_name,
            discovered_reason=tuple(discovered_reason),
            metrics=metrics,
            source_endpoints=candidate_endpoints,
            source="KIS_API",
            scan_run_id=scan_id,
            included=included,
            excluded_reason=reason,
        ))

    included = sum(1 for c in candidates if c.included)
    excluded = sum(1 for c in candidates if not c.included)

    return ScanRunResult(
        scan_run_id=scan_id,
        scanner_type=scanner_type,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        market_regime=market_regime,
        collected_count=len(stocks),
        excluded_count=excluded,
        included_count=included,
        candidates=tuple(candidates),
        source_endpoints=tuple(endpoints) if endpoints else (),
        data_quality_warnings=(),
    )


def run_all_scanners(
    stocks: list[dict[str, Any]],
    market_regime: str = "UNKNOWN",
    config: dict[str, Any] | None = None,
    scan_run_id: str | None = None,
) -> list[ScanRunResult]:
    """전체 Scanner Type 실행

    동일한 stock 데이터를 4개 Scanner Type 모두로 실행한다.
    Market Regime에 따라 Scanner 활성화는 각 필터 함수에서 처리된다.

    Args:
        stocks: 종목별 metric dicts
        market_regime: 현재 시장 상태
        config: Scanner 설정 오버라이드
        scan_run_id: 스캔 실행 ID (없으면 자동 생성)

    Returns:
        Scanner Type별 ScanRunResult 리스트 (4개)
    """
    results: list[ScanRunResult] = []
    for scanner_type in ScannerType:
        result = run_scanner(
            stocks, scanner_type, market_regime, config, scan_run_id
        )
        results.append(result)
    return results
