"""RiskContext — Risk Engine 실행 컨텍스트"""
from __future__ import annotations

from dataclasses import dataclass

from market_regime.regime_result import MarketRegimeResult
from session.session_state import TradingSessionState


@dataclass(frozen=True)
class RiskContext:
    """Risk Engine 평가 컨텍스트

    시장/세션/계좌 상태를 포함한 현재 시스템 상태.
    Risk Engine의 모든 검증은 이 컨텍스트를 기준으로 수행된다.
    """
    market_regime_result: MarketRegimeResult
    session_state: TradingSessionState
    emergency_stop: bool
    live_trading_enabled: bool
    current_positions: frozenset[str]
    pending_orders: frozenset[str]
    today_realized_pnl: int
    daily_loss_limit: int
    data_quality_warnings: tuple[str, ...] = ()
