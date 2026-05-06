"""Live Trading Runner (skeleton).

Purpose of this phase:
- Prevent confusion: dry-run logic must not be mistaken for live trading.
- Provide an explicit LIVE runner entrypoint that is safe-by-default.

Rules:
- This runner MUST NOT submit real orders in this Phase.
- If not configured, return BLOCKED_NOT_CONFIGURED / NOT_READY.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveTradingTickResult:
    mode: str
    status: str
    reason: str

    def to_dict(self) -> dict:
        return {"mode": self.mode, "status": self.status, "reason": self.reason}


class LiveTradingRunner:
    """Skeleton runner.

    In a later phase, this will orchestrate:
      Scanner -> Quant -> Strategy -> Risk -> SafetyGate -> OrderSubmit

    For now, it's intentionally blocked until explicitly configured.
    """

    def __init__(self, configured: bool = False):
        self._configured = bool(configured)

    def run_tick(self, session: str) -> LiveTradingTickResult:
        if not self._configured:
            return LiveTradingTickResult(
                mode="LIVE",
                status="BLOCKED_NOT_CONFIGURED",
                reason="LIVE_TRADING_RUNNER_NOT_READY",
            )
        # Even if configured flag is true, do not submit orders in this phase.
        return LiveTradingTickResult(
            mode="LIVE",
            status="BLOCKED_NOT_IMPLEMENTED",
            reason="LIVE_ORDER_SUBMISSION_NOT_IMPLEMENTED_IN_SAFETY_PHASE",
        )
