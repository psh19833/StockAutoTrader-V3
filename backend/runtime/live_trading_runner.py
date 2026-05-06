"""Live Trading Runner (guarded live-auto readiness).

This module enables LIVE mode only when strict guardrails pass.
No direct order execution is performed here without downstream gate chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LiveTradingTickResult:
    mode: str
    status: str
    reason: str
    ready: bool = False
    block_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status,
            "reason": self.reason,
            "ready": self.ready,
            "block_reasons": list(self.block_reasons),
        }


class LiveTradingRunner:
    """Guarded live runner.

    Pipeline execution is intentionally conservative:
    - LIVE starts only when all prerequisite checks pass.
    - Any missing/unknown source condition blocks new buy/order path.
    """

    def __init__(self, configured: bool = False):
        self._configured = bool(configured)

    def evaluate_start_readiness(self, checks: dict[str, bool]) -> LiveTradingTickResult:
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            return LiveTradingTickResult(
                mode="LIVE",
                status="BLOCKED_PRECONDITION_FAILED",
                reason="LIVE_START_PRECONDITION_FAILED",
                ready=False,
                block_reasons=failed,
            )
        return LiveTradingTickResult(
            mode="LIVE",
            status="READY",
            reason="LIVE_AUTO_READY",
            ready=True,
            block_reasons=[],
        )

    def run_tick(self, session: str, ready: bool, block_reasons: list[str] | None = None) -> LiveTradingTickResult:
        if not self._configured:
            return LiveTradingTickResult(
                mode="LIVE",
                status="BLOCKED_NOT_CONFIGURED",
                reason="LIVE_TRADING_RUNNER_NOT_READY",
                ready=False,
                block_reasons=["SAT3_ENABLE_LIVE_RUNNER_FALSE"],
            )
        if session != "REGULAR_MARKET":
            return LiveTradingTickResult(
                mode="LIVE",
                status="BLOCKED_SESSION",
                reason="SESSION_NOT_REGULAR_MARKET",
                ready=False,
                block_reasons=["SESSION_NOT_REGULAR_MARKET"],
            )
        if not ready:
            return LiveTradingTickResult(
                mode="LIVE",
                status="BLOCKED_PRECONDITION_FAILED",
                reason="LIVE_START_PRECONDITION_FAILED",
                ready=False,
                block_reasons=list(block_reasons or []),
            )

        return LiveTradingTickResult(
            mode="LIVE",
            status="LIVE_PIPELINE_TICK_EXECUTED",
            reason="LIVE_GUARDS_PASSED",
            ready=True,
            block_reasons=[],
        )
