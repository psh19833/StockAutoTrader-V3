"""Risk Engine — SignalIntent 최종 검증

Risk Engine은 실전 주문 전 최종 방어막이다.
모든 Signal은 Risk Engine 승인 없이 주문으로 전환될 수 없다.

검증 순서:
  1. LIVE_TRADING_ENABLED
  2. Emergency Stop
  3. Session State
  4. Market Regime
  5. Duplicate Order/Position
  6. Data Quality Warnings
  7. Amount Limit
  8. Position Count Limit
  9. Daily Loss Limit
  10. Final Decision

핵심 안전 원칙:
  - RiskDecision APPROVED도 실제 주문이 아니다. SafetyGate와 Order Submitter가 별도 필요.
  - data_quality_warnings가 있으면 RiskDecision은 항상 REJECTED이다.
  - 모든 실패 항목은 failed_items에 보존된다.
  - amount limit / position count limit은 RiskLimits를 통해 적용된다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from strategy.signal import StrategySignal
from risk.risk_types import RiskDecisionStatus, RiskRejectReason
from risk.risk_decision import RiskDecision
from risk.risk_context import RiskContext
from risk.risk_config import RiskLimits
from session.session_state import TradingSessionState, BUY_BLOCKED_STATES


@dataclass(frozen=True)
class _CheckResult:
    """개별 검사 결과"""
    allowed: bool
    reason_code: RiskRejectReason | None = None
    check_name: str = ""


# ── 개별 검증 함수들 ──


def check_live_trading_enabled(enabled: bool) -> _CheckResult:
    if not enabled:
        return _CheckResult(False, RiskRejectReason.LIVE_TRADING_DISABLED,
                            "live_trading_enabled")
    return _CheckResult(True, check_name="live_trading_enabled")


def check_emergency_stop(active: bool) -> _CheckResult:
    if active:
        return _CheckResult(False, RiskRejectReason.EMERGENCY_STOP_BLOCKED,
                            "emergency_stop")
    return _CheckResult(True, check_name="emergency_stop")


def check_session_state(state: TradingSessionState, side: str) -> _CheckResult:
    # SELL은 더 관대한 세션 정책 적용 (청산 허용)
    if side == "SELL":
        if state in {TradingSessionState.CLOSED_HOLIDAY,
                     TradingSessionState.SESSION_STATE_UNKNOWN}:
            return _CheckResult(False, RiskRejectReason.SESSION_BLOCKED,
                                "session_state")
        return _CheckResult(True, check_name="session_state")

    if state in BUY_BLOCKED_STATES:
        return _CheckResult(False, RiskRejectReason.SESSION_BLOCKED,
                            "session_state")
    return _CheckResult(True, check_name="session_state")


def check_market_regime(allow_new_buy: bool, side: str) -> _CheckResult:
    if side == "SELL":
        return _CheckResult(True, check_name="market_regime")
    if not allow_new_buy:
        return _CheckResult(False, RiskRejectReason.MARKET_REGIME_BLOCKED,
                            "market_regime")
    return _CheckResult(True, check_name="market_regime")


def check_duplicate_order(symbol: str, pending_orders: frozenset[str]) -> _CheckResult:
    if symbol in pending_orders:
        return _CheckResult(False, RiskRejectReason.DUPLICATE_ORDER_BLOCKED,
                            "duplicate_order")
    return _CheckResult(True, check_name="duplicate_order")


def check_duplicate_position(symbol: str, positions: frozenset[str], side: str = "BUY") -> _CheckResult:
    # SELL은 기존 포지션이 있어야 하므로 중복 검사 제외
    if side == "SELL":
        return _CheckResult(True, check_name="duplicate_position")
    if symbol in positions:
        return _CheckResult(False, RiskRejectReason.SYMBOL_EXPOSURE_BLOCKED,
                            "duplicate_position")
    return _CheckResult(True, check_name="duplicate_position")


def check_daily_loss_limit(pnl: int, limit: int) -> _CheckResult:
    if pnl < 0 and abs(pnl) >= limit:
        return _CheckResult(False, RiskRejectReason.DAILY_LOSS_LIMIT_BLOCKED,
                            "daily_loss_limit")
    return _CheckResult(True, check_name="daily_loss_limit")


# ── STEP 7: data_quality_warnings 차단 ──

def check_data_quality_warnings(
    data_quality_warnings: tuple[str, ...],
) -> _CheckResult:
    """data_quality_warnings가 있으면 차단

    warning 문자열에 민감 정보가 포함될 수 있으므로 reason_text에는
    전체 warning을 직접 넣지 않고 개수만 표시한다.
    """
    if data_quality_warnings:
        return _CheckResult(
            False,
            RiskRejectReason.DATA_QUALITY_BLOCKED,
            "data_quality_warnings",
        )
    return _CheckResult(True, check_name="data_quality_warnings")


# ── STEP 8: 금액/포지션 한도 체크 ──

def check_amount_limit(
    requested_amount: int,
    limits: RiskLimits,
    side: str,
) -> _CheckResult:
    """요청 금액이 종목당 최대 금액을 초과하는지 확인"""
    if requested_amount > 0 and requested_amount > limits.max_amount_per_symbol:
        return _CheckResult(
            False,
            RiskRejectReason.POSITION_LIMIT_BLOCKED,
            "amount_limit",
        )
    return _CheckResult(True, check_name="amount_limit")


def check_position_limit(
    current_positions: int,
    limits: RiskLimits,
    side: str,
) -> _CheckResult:
    """포지션 수 한도 확인 (신규 BUY만, SELL은 제외)"""
    if side == "SELL":
        return _CheckResult(True, check_name="position_limit")
    if current_positions >= limits.max_position_count:
        return _CheckResult(
            False,
            RiskRejectReason.POSITION_LIMIT_BLOCKED,
            "position_limit",
        )
    return _CheckResult(True, check_name="position_limit")


# ── 메인 평가 함수 ──


def evaluate_risk(
    signal: StrategySignal,
    context: RiskContext,
    requested_amount: int = 0,
    limits: RiskLimits | None = None,
) -> RiskDecision:
    """Signal + Context → RiskDecision

    모든 검증을 수행하고 최종 판단을 반환한다.

    Args:
        signal: StrategySignal
        context: RiskContext (시장/세션/계좌 상태)
        requested_amount: 요청 금액 (기본 0 — 실전 경로에서는 SafetyGate가 별도 확인)
        limits: 리스크 제한값 (기본 RiskLimits)

    Returns:
        RiskDecision (APPROVED / REJECTED)
    """
    if limits is None:
        limits = RiskLimits()

    checked_items: list[str] = []
    # STEP 9: 모든 실패 항목 보존
    failed_items: list[str] = []
    failed_codes: list[str] = []
    reject_reason: RiskRejectReason | None = None
    reject_text: str = ""

    checks = [
        check_live_trading_enabled(context.live_trading_enabled),
        check_emergency_stop(context.emergency_stop),
        check_session_state(context.session_state, signal.side),
        check_market_regime(
            context.market_regime_result.allow_new_buy, signal.side
        ),
        check_duplicate_order(signal.symbol, context.pending_orders),
        check_duplicate_position(signal.symbol, context.current_positions, signal.side),
        check_data_quality_warnings(context.data_quality_warnings),
        check_amount_limit(requested_amount, limits, signal.side),
        check_position_limit(
            len(context.current_positions), limits, signal.side
        ),
        check_daily_loss_limit(
            context.today_realized_pnl, context.daily_loss_limit
        ),
    ]

    for chk in checks:
        checked_items.append(chk.check_name)
        if not chk.allowed:
            failed_items.append(chk.check_name)
            if chk.reason_code:
                failed_codes.append(chk.reason_code.value)
            if reject_reason is None:
                reject_reason = chk.reason_code
                reject_text = f"{chk.reason_code.value if chk.reason_code else 'UNKNOWN'}: check failed"

    allowed = reject_reason is None

    return RiskDecision(
        risk_decision_id=f"rd_{uuid.uuid4().hex[:12]}",
        signal_id=signal.signal_id,
        correlation_id=signal.correlation_id,
        symbol=signal.symbol,
        side=signal.side,
        status=RiskDecisionStatus.APPROVED if allowed else RiskDecisionStatus.REJECTED,
        allowed=allowed,
        reason_code=reject_reason.value if reject_reason else "APPROVED",
        reason_text=reject_text if reject_text else "All risk checks passed",
        checked_items=tuple(checked_items),
        failed_items=tuple(failed_items),
        market_regime=signal.market_regime,
        session_state=context.session_state.value,
        requested_amount=requested_amount,
    )
