"""N13: Live Order Safety Gate — multi-layer order blocking."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GateResult(Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


@dataclass
class SafetyGateCheck:
    """Single safety check result."""
    name: str
    passed: bool
    reason: str = ""


@dataclass
class SafetyGateResult:
    """Aggregate safety gate result."""
    passed: bool
    checks: list[SafetyGateCheck] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)


class LiveOrderSafetyGate:
    """Multi-layer safety gate for order submission.

    All conditions must pass before any order is submitted.
    Defaults to BLOCKED when any condition fails.
    """

    def __init__(self):
        self._emergency_stop = False

    @property
    def emergency_stop(self) -> bool:
        return self._emergency_stop

    @emergency_stop.setter
    def emergency_stop(self, value: bool) -> None:
        self._emergency_stop = value

    def check(
        self,
        live_trading_enabled: bool,
        session: str,
        market_regime: str,
        risk_approved: bool,
        quote_stale: Optional[bool] = None,
        orderbook_stale: Optional[bool] = None,
        max_daily_loss_exceeded: Optional[bool] = None,
        duplicate_order: Optional[bool] = None,
        ws_connected: Optional[bool] = None,
    ) -> SafetyGateResult:
        """Run all safety checks (10-layer).

        Returns BLOCKED if any check fails.
        """
        checks = [
            SafetyGateCheck("LIVE_TRADING_ENABLED", live_trading_enabled,
                            "LIVE_TRADING_ENABLED must be true"),
            SafetyGateCheck("EMERGENCY_STOP", not self._emergency_stop,
                            "Emergency stop is active"),
            SafetyGateCheck("SESSION", session == "REGULAR_MARKET",
                            f"Session {session} is not REGULAR_MARKET"),
            SafetyGateCheck("MARKET_REGIME", market_regime not in ("BEAR", "UNKNOWN"),
                            f"Market regime {market_regime} blocks orders"),
            SafetyGateCheck("RISK_APPROVED", risk_approved,
                            "Risk decision not approved"),
            SafetyGateCheck("QUOTE_FRESH", quote_stale is False,
                            "Quote data is stale or freshness is unknown"),
            SafetyGateCheck("ORDERBOOK_FRESH", orderbook_stale is False,
                            "Orderbook data is stale or freshness is unknown"),
            SafetyGateCheck("MAX_DAILY_LOSS", max_daily_loss_exceeded is False,
                            "Max daily loss exceeded or loss state is unknown"),
            SafetyGateCheck("DUPLICATE_ORDER", duplicate_order is False,
                            "Duplicate order detected or duplicate state is unknown"),
            SafetyGateCheck("WS_CONNECTED", ws_connected is True,
                            "WebSocket disconnected or connection state is unknown"),
        ]

        passed = all(c.passed for c in checks)
        block_reasons = [c.reason for c in checks if not c.passed]

        return SafetyGateResult(
            passed=passed,
            checks=checks,
            block_reasons=block_reasons,
        )
