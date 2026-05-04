"""Risk Engine — SignalIntent 최종 검증

Risk Engine은 실전 주문 전 최종 방어막이다.
모든 Signal은 Risk Engine 승인 없이 주문으로 전환될 수 없다.

검증 순서:
  1. LIVE_TRADING_ENABLED
  2. Emergency Stop
  3. Session State
  4. Market Regime
  5. Duplicate Order/Position
  6. Daily Loss Limit
  7. Final Decision
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from strategy.signal import StrategySignal
from risk.risk_types import RiskDecisionStatus, RiskRejectReason
from risk.risk_decision import RiskDecision
from risk.risk_context import RiskContext
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


def check_duplicate_position(symbol: str, positions: frozenset[str]) -> _CheckResult:
    if symbol in positions:
        return _CheckResult(False, RiskRejectReason.SYMBOL_EXPOSURE_BLOCKED,
                            "duplicate_position")
    return _CheckResult(True, check_name="duplicate_position")


def check_daily_loss_limit(pnl: int, limit: int) -> _CheckResult:
    if pnl < 0 and abs(pnl) >= limit:
        return _CheckResult(False, RiskRejectReason.DAILY_LOSS_LIMIT_BLOCKED,
                            "daily_loss_limit")
    return _CheckResult(True, check_name="daily_loss_limit")


# ── 메인 평가 함수 ──


def evaluate_risk(
    signal: StrategySignal,
    context: RiskContext,
) -> RiskDecision:
    """Signal + Context → RiskDecision

    모든 검증을 순차적으로 수행하고 최종 판단을 반환한다.

    Args:
        signal: StrategySignal
        context: RiskContext (시장/세션/계좌 상태)

    Returns:
        RiskDecision (APPROVED / REJECTED)
    """
    checked_items: list[str] = []
    failed_items: list[str] = []
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
        check_duplicate_position(signal.symbol, context.current_positions),
        check_daily_loss_limit(
            context.today_realized_pnl, context.daily_loss_limit
        ),
    ]

    for chk in checks:
        checked_items.append(chk.check_name)
        if not chk.allowed and reject_reason is None:
            reject_reason = chk.reason_code
            reject_text = f"{chk.reason_code.value if chk.reason_code else 'UNKNOWN'}: check failed"
            failed_items.append(chk.check_name)

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
        requested_amount=0,
    )
