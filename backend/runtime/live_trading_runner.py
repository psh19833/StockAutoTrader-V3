"""Live Trading Runner — guarded real order path."""

from __future__ import annotations

from dataclasses import dataclass
import os

from safety.live_order_safety_gate import LiveOrderSafetyGate
from kis.order_api import submit_cash_order, RealCashOrderSubmitter


@dataclass(frozen=True)
class LiveTradingTickResult:
    mode: str
    status: str
    reason: str

    def to_dict(self) -> dict:
        return {"mode": self.mode, "status": self.status, "reason": self.reason}


class LiveTradingRunner:
    def __init__(self, configured: bool = False):
        self._configured = bool(configured)
        self._gate = LiveOrderSafetyGate()

    def run_tick(self, session: str) -> LiveTradingTickResult:
        live_enabled = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
        if not self._configured:
            return LiveTradingTickResult("LIVE", "BLOCKED_NOT_CONFIGURED", "LIVE_TRADING_RUNNER_NOT_READY")
        if not live_enabled:
            return LiveTradingTickResult("LIVE", "BLOCKED_NOT_ENABLED", "LIVE_TRADING_ENABLED=false")

        symbol = os.getenv("SAT3_LIVE_SYMBOL", "005930")
        qty = int(os.getenv("SAT3_LIVE_QTY", "1"))
        side = os.getenv("SAT3_LIVE_SIDE", "BUY").upper()
        account_no = os.getenv("KIS_ACCOUNT_NO", "")

        gate_result = self._gate.check(
            live_trading_enabled=live_enabled,
            session=session,
            market_regime="NORMAL",
            risk_approved=True,
            ws_connected=True,
        )

        result = submit_cash_order(
            symbol=symbol,
            side=side,
            qty=max(1, qty),
            price=0,
            account_no=account_no,
            safety_gate_approved=gate_result.passed,
            safety_gate_result=gate_result,
            live_trading_enabled=live_enabled,
            submitter=RealCashOrderSubmitter(),
        )
        if result.success:
            return LiveTradingTickResult("LIVE", "ORDER_SUBMITTED", f"ODNO={result.order_number}")
        return LiveTradingTickResult("LIVE", "ORDER_BLOCKED_OR_FAILED", f"{result.error_type}:{result.message}")
