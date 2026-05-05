"""Scoring Calculator — 후보 점수 계산 엔진

ScannerCandidate + MarketRegimeResult → QuantCandidateScore
점수 계산과 Decision 결정을 수행한다.

Quant PASS는 매수 신호가 아니다.
Strategy Engine에 넘길 수 있는 후보라는 의미일 뿐이다.

핵심 안전 원칙:
  - Scanner에서 제외된 후보(excluded)는 무조건 REJECT (metric이 좋아도 PASS 불가).
  - data_quality_warnings (STALE, DISCONNECTED, DATA_UNAVAILABLE 등)가 있으면 Quant PASS 불가.
  - 음수 change(하락률)를 긍정 모멘텀으로 가산하지 않는다. 급락은 별도 risk penalty로 처리.
"""
from __future__ import annotations

import uuid
from typing import Any

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate
from market_regime.regime_result import MarketRegimeResult
from quant.candidate_score import QuantCandidateScore, QuantDecision
from quant.scoring_config import (
    DEFAULT_SCORING_CONFIG,
    get_scanner_specific_config,
)


# 기본 가중치 (모든 점수 0~10, 최대 합 70)
DEFAULT_COMMON_WEIGHTS: dict[str, float] = {
    "liquidity": 1.0,
    "spread": 1.0,
    "volume": 1.0,
    "momentum": 1.0,
    "trend": 1.0,
    "orderbook": 1.0,
    "volatility_safety": 1.0,
}

# 0~10 범위 클램프
def _clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, value))


# ── 공통 점수 계산 ──


def compute_common_scores(metrics: dict[str, Any]) -> dict[str, float]:
    """공통 점수 계산

    각 점수는 0~10 범위로 정규화된다.
    metric이 없으면 보수적으로 낮은 점수(≤3)를 반환한다.
    """
    # 유동성: 거래대금 기준 (100억 이상 → 10, 10억 미만 → 1)
    tv = metrics.get("trading_value", 0) or 0
    tv_rank = metrics.get("trading_value_rank")
    if tv >= 100_000_000_000:
        liquidity_score = 10.0
    elif tv >= 50_000_000_000:
        liquidity_score = 8.0
    elif tv >= 20_000_000_000:
        liquidity_score = 6.0
    elif tv >= 5_000_000_000:
        liquidity_score = 4.0
    elif tv >= 1_000_000_000:
        liquidity_score = 2.0
    else:
        liquidity_score = 1.0

    # 순위 보정 (상위 30위면 +1)
    if tv_rank is not None and tv_rank <= 30:
        liquidity_score += 1.0
    liquidity_score = _clamp(liquidity_score)

    # 스프레드: 0.01% 이하 → 10, 0.5% 이상 → 1
    spread = metrics.get("spread_rate", 1.0) or 1.0
    if spread <= 0.01:
        spread_score = 10.0
    elif spread <= 0.05:
        spread_score = 8.0
    elif spread <= 0.1:
        spread_score = 6.0
    elif spread <= 0.3:
        spread_score = 4.0
    elif spread <= 0.5:
        spread_score = 2.0
    else:
        spread_score = 1.0
    spread_score = _clamp(spread_score)

    # 거래량: 절대량 + 평균 대비 비율
    vol = metrics.get("volume", 0) or 0
    vol_ratio = metrics.get("volume_ratio_vs_recent_avg", 0) or 0
    vol_base = min(5.0, vol / 1_000_000)
    vol_bonus = min(5.0, vol_ratio * 1.5)
    volume_score = _clamp(vol_base + vol_bonus)

    # 모멘텀: 등락률 + 체결강도
    # STEP 6: 음수 change를 긍정 모멘텀으로 가산하지 않음
    # change <= 0 이면 change_score = 0
    # 급락은 risk penalty나 volatility penalty로 별도 반영
    change = metrics.get("intraday_change_rate", 0) or 0
    exec_str = metrics.get("execution_strength", 0) or 0
    if change > 0:
        change_score = _clamp(change * 1.5)
    else:
        change_score = 0.0
    exec_score = _clamp(exec_str / 20.0)
    momentum_score = _clamp((change_score + exec_score) / 2)

    # 추세: 당일 고점 대비 근접도
    price = metrics.get("current_price", 0) or 0
    high = metrics.get("intraday_high", price) or price
    if price > 0 and high > 0:
        proximity = price / high
        trend_score = _clamp(proximity * 10.0)
    else:
        trend_score = 3.0

    # 호가창 점수 (정보 없으면 낮은 점수)
    orderbook_score = 3.0

    # 변동성 안전: 변동성 비율이 낮을수록 안전
    vol_ratio_metric = metrics.get("volatility_ratio", 1.0) or 1.0
    if vol_ratio_metric <= 0.5:
        volatility_safety_score = 9.0
    elif vol_ratio_metric <= 1.0:
        volatility_safety_score = 7.0
    elif vol_ratio_metric <= 2.0:
        volatility_safety_score = 4.0
    else:
        volatility_safety_score = 1.0
    volatility_safety_score = _clamp(volatility_safety_score)

    return {
        "liquidity_score": liquidity_score,
        "spread_score": spread_score,
        "volume_score": volume_score,
        "momentum_score": momentum_score,
        "trend_score": trend_score,
        "orderbook_score": orderbook_score,
        "volatility_safety_score": volatility_safety_score,
    }


# ── RAPID_SURGE 전용 점수 ──


def compute_rapid_surge_scores(metrics: dict[str, Any]) -> dict[str, float]:
    """RAPID_SURGE 전용 점수 계산"""
    change = metrics.get("intraday_change_rate", 0) or 0
    vol_ratio = metrics.get("volume_ratio_vs_recent_avg", 0) or 0
    price = metrics.get("current_price", 0) or 0
    high = metrics.get("intraday_high", price) or price
    vi_status = metrics.get("vi_status", "UNKNOWN")
    pullback = metrics.get("pullback_from_high", 0) or 0

    # 급등 속도: 등락률 10% 이상 → 10
    surge_velocity = _clamp(change * 1.0)

    # 거래량 폭증: 평균 대비 10배 → 10
    volume_burst = _clamp(vol_ratio * 1.0)

    # 당일 고점 근접도
    if price > 0 and high > 0:
        proximity = price / high
        intraday_high_prox = _clamp(proximity * 10.0)
    else:
        intraday_high_prox = 5.0

    # VI 패널티
    vi_penalty = 8.0 if vi_status == "ACTIVE" else 0.0

    # 눌림 실패 패널티
    pullback_penalty = _clamp(pullback * 1.5)

    return {
        "surge_velocity_score": surge_velocity,
        "volume_burst_score": volume_burst,
        "intraday_high_proximity_score": intraday_high_prox,
        "vi_proximity_penalty": vi_penalty,
        "pullback_failure_penalty": pullback_penalty,
    }


# ── PULLBACK_REBOUND 전용 점수 ──


def compute_pullback_scores(metrics: dict[str, Any]) -> dict[str, float]:
    """PULLBACK_REBOUND 전용 점수 계산"""
    prior_gain = metrics.get("prior_intraday_gain", 0) or 0
    pullback = metrics.get("pullback_from_high", 0) or 0
    rebound_vol = metrics.get("rebound_volume_ratio", 0) or 0
    support = metrics.get("support_holding_score", 0) or 0

    # 이전 상승 강도
    prior_strength = _clamp(prior_gain * 1.0)

    # 눌림 깊이 (적절한 눌림일수록 높음: 1~3%가 이상적)
    if pullback <= 0.5:
        pullback_depth = 8.0  # 너무 얕은 눌림도 좋음
    elif pullback <= 3.0:
        pullback_depth = _clamp(10.0 - (pullback - 0.5) * 1.5)
    elif pullback <= 5.0:
        pullback_depth = _clamp(6.0 - (pullback - 3.0) * 2.0)
    else:
        pullback_depth = 1.0

    # 반등 확인
    rebound_conf = _clamp(rebound_vol * 3.0)

    # 지지 유지
    support_score = _clamp(support * 1.0)

    return {
        "prior_strength_score": prior_strength,
        "pullback_depth_score": pullback_depth,
        "rebound_confirmation_score": rebound_conf,
        "support_holding_score": support_score,
    }


# ── Decision 결정 ──


def determine_decision(
    final_score: float,
    regime_result: MarketRegimeResult,
    pass_threshold: float,
    watch_threshold: float,
) -> tuple[str, tuple[str, ...]]:
    """최종 Decision 결정

    Args:
        final_score: 보정 완료된 최종 점수
        regime_result: 시장 상태 평가 결과
        pass_threshold: PASS 기준
        watch_threshold: WATCH 기준

    Returns:
        (decision, reasons)
    """
    reasons: list[str] = []

    # Market Regime 차단 우선
    if not regime_result.allow_new_buy:
        reasons.append(f"MarketRegime={regime_result.regime.value}: new buy blocked")
        return (QuantDecision.REJECT.value, tuple(reasons))

    if final_score >= pass_threshold:
        return (QuantDecision.PASS.value, tuple(reasons))
    elif final_score >= watch_threshold:
        reasons.append(f"Score {final_score:.1f} >= watch threshold {watch_threshold}")
        return (QuantDecision.WATCH.value, tuple(reasons))
    else:
        reasons.append(f"Score {final_score:.1f} below watch threshold {watch_threshold}")
        return (QuantDecision.REJECT.value, tuple(reasons))


# ── 후보 평가 ──


def evaluate_candidate(
    candidate: ScannerCandidate,
    regime_result: MarketRegimeResult,
    config: dict[str, Any] | None = None,
) -> QuantCandidateScore:
    """ScannerCandidate 단일 평가

    공통 점수 + Scanner Type별 점수 + Market Regime 보정
    → 최종 점수 및 Decision

    Args:
        candidate: Scanner에서 발굴한 후보
        regime_result: 시장 상태 평가 결과
        config: 점수 설정 오버라이드

    Returns:
        QuantCandidateScore (PASS는 매수 신호가 아님)
    """
    # ── STEP 1: Scanner excluded 후보는 바로 REJECT ──
    # excluded 후보는 metric이 좋아도 Quant PASS 불가
    if not candidate.included:
        return QuantCandidateScore(
            symbol=candidate.symbol,
            scanner_type=candidate.scanner_type.value,
            scan_run_id=candidate.scan_run_id,
            evaluation_id=uuid.uuid4().hex[:12],
            final_score=0.0,
            decision=QuantDecision.REJECT,
            reasons=("SCANNER_EXCLUDED", candidate.excluded_reason or "excluded_by_scanner"),
            source_endpoints=candidate.source_endpoints,
            data_quality_warnings=(),
        )

    # ── STEP 5: data_quality_warnings 차단 ──
    # critical data quality issue가 있으면 Quant PASS 불가
    dq_warnings = regime_result.data_quality_warnings or ()
    critical_keywords = (
        "STALE", "DISCONNECTED", "DATA_UNAVAILABLE",
        "KIS_QUERY_FAILED", "ORDERBOOK_MISSING", "QUOTE_MISSING",
    )
    has_critical = any(
        any(kw in (w or "") for kw in critical_keywords)
        for w in dq_warnings
    )
    if has_critical:
        return QuantCandidateScore(
            symbol=candidate.symbol,
            scanner_type=candidate.scanner_type.value,
            scan_run_id=candidate.scan_run_id,
            evaluation_id=uuid.uuid4().hex[:12],
            final_score=0.0,
            decision=QuantDecision.REJECT,
            reasons=("DATA_QUALITY_BLOCKED",) + dq_warnings,
            source_endpoints=candidate.source_endpoints,
            data_quality_warnings=dq_warnings,
        )

    cfg = DEFAULT_SCORING_CONFIG
    if config:
        from quant.scoring_config import get_scoring_config
        cfg = get_scoring_config(config)

    metrics = candidate.metrics

    # 공통 점수
    common = compute_common_scores(metrics)
    base_score = (
        common["liquidity_score"]
        + common["spread_score"]
        + common["volume_score"]
        + common["momentum_score"]
        + common["trend_score"]
        + common["orderbook_score"]
        + common["volatility_safety_score"]
    )

    # Scanner Type별 점수
    scanner_type = candidate.scanner_type.value
    rs_scores: dict[str, float] = {}
    pullback_scores: dict[str, float] = {}
    scanner_bonus = 0.0

    if scanner_type == ScannerType.RAPID_SURGE.value:
        rs_scores = compute_rapid_surge_scores(metrics)
        scanner_bonus = (
            rs_scores["surge_velocity_score"]
            + rs_scores["volume_burst_score"]
            + rs_scores["intraday_high_proximity_score"]
            - rs_scores["vi_proximity_penalty"]
            - rs_scores["pullback_failure_penalty"]
        )
    elif scanner_type == ScannerType.PULLBACK_REBOUND.value:
        pullback_scores = compute_pullback_scores(metrics)
        scanner_bonus = (
            pullback_scores["prior_strength_score"]
            + pullback_scores["pullback_depth_score"]
            + pullback_scores["rebound_confirmation_score"]
            + pullback_scores["support_holding_score"]
        )
    else:
        # LIQUIDITY_MOMENTUM / BREAKOUT: 공통 점수만 사용
        pass

    scanner_bonus = _clamp(scanner_bonus)

    # Symbol Risk Penalty
    symbol_risk = 0.0
    if metrics.get("vi_status") == "ACTIVE":
        symbol_risk += 5.0
    if metrics.get("is_management_issue"):
        symbol_risk += 10.0
    if metrics.get("is_investment_warning"):
        symbol_risk += 10.0
    symbol_risk = _clamp(symbol_risk)

    # Market Regime 보정
    regime_adj = regime_result.candidate_score_adjustment

    # 최종 점수
    final_score = base_score + scanner_bonus - symbol_risk + regime_adj
    final_score = _clamp(final_score, lo=-10.0, hi=100.0)

    # Threshold 결정 (Scanner Type별)
    scanner_cfg = get_scanner_specific_config(scanner_type)
    pass_threshold = scanner_cfg.get("pass_threshold", cfg.pass_threshold)
    watch_threshold = scanner_cfg.get("watch_threshold", cfg.watch_threshold)

    # BULL 시장 threshold 완화
    regime_policy = cfg.regime_policies.get(regime_result.regime.value, {})
    threshold_bonus = regime_policy.get("pass_threshold_bonus")
    if threshold_bonus is not None:
        pass_threshold += float(threshold_bonus)

    decision, reasons = determine_decision(
        final_score, regime_result, pass_threshold, watch_threshold
    )

    # Market Regime 차단 사유 추가
    if not regime_result.allow_new_buy:
        reasons = ("MarketRegimeBlocked",) + reasons

    return QuantCandidateScore(
        symbol=candidate.symbol,
        scanner_type=scanner_type,
        scan_run_id=candidate.scan_run_id,
        evaluation_id=uuid.uuid4().hex[:12],
        liquidity_score=common["liquidity_score"],
        spread_score=common["spread_score"],
        volume_score=common["volume_score"],
        momentum_score=common["momentum_score"],
        trend_score=common["trend_score"],
        orderbook_score=common["orderbook_score"],
        volatility_safety_score=common["volatility_safety_score"],
        market_regime_adjustment=regime_adj,
        symbol_risk_penalty=symbol_risk,
        final_score=final_score,
        decision=QuantDecision(decision),
        reasons=reasons,
        surge_velocity_score=rs_scores.get("surge_velocity_score", 0.0),
        volume_burst_score=rs_scores.get("volume_burst_score", 0.0),
        intraday_high_proximity_score=rs_scores.get("intraday_high_proximity_score", 0.0),
        vi_proximity_penalty=rs_scores.get("vi_proximity_penalty", 0.0),
        pullback_failure_penalty=rs_scores.get("pullback_failure_penalty", 0.0),
        prior_strength_score=pullback_scores.get("prior_strength_score", 0.0),
        pullback_depth_score=pullback_scores.get("pullback_depth_score", 0.0),
        rebound_confirmation_score=pullback_scores.get("rebound_confirmation_score", 0.0),
        support_holding_score=pullback_scores.get("support_holding_score", 0.0),
        source_endpoints=candidate.source_endpoints,
        data_quality_warnings=regime_result.data_quality_warnings,
    )


# ── Batch 평가 ──


def evaluate_candidates(
    candidates: list,
    regime_result: MarketRegimeResult,
    config: dict[str, Any] | None = None,
) -> list:
    """ScannerCandidate 리스트 일괄 평가

    각 후보를 evaluate_candidate()로 평가하여 QuantCandidateScore 리스트 반환.
    제외된 후보(included=False)도 평가하여 제외 사유가 포함된 결과를 생성한다.

    Args:
        candidates: ScannerCandidate 리스트
        regime_result: 시장 상태 평가 결과
        config: 점수 설정 오버라이드

    Returns:
        QuantCandidateScore 리스트
    """
    results: list = []
    for candidate in candidates:
        score = evaluate_candidate(candidate, regime_result, config)
        results.append(score)
    return results


def evaluate_scan_result(
    scan_result,
    regime_result: MarketRegimeResult,
    config: dict[str, Any] | None = None,
) -> list:
    """ScanRunResult → 일괄 Quant 평가

    ScanRunResult의 모든 후보를 Quant로 평가한다.

    Args:
        scan_result: Scanner 실행 결과
        regime_result: 시장 상태 평가 결과
        config: 점수 설정 오버라이드

    Returns:
        QuantCandidateScore 리스트
    """
    from scanner.scan_result import ScanRunResult
    return evaluate_candidates(
        list(scan_result.candidates), regime_result, config
    )