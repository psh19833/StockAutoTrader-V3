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
        quote_stale: bool = False,
        orderbook_stale: bool = False,
        max_daily_loss_exceeded: bool = False,
        max_position_exceeded: bool = False,
        duplicate_order: bool = False,
        ws_connected: bool = True,
    ) -> SafetyGateResult:
        """Run all safety checks.

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
            SafetyGateCheck("QUOTE_FRESH", not quote_stale,
                            "Quote data is stale"),
            SafetyGateCheck("ORDERBOOK_FRESH", not orderbook_stale,
                            "Orderbook data is stale"),
            SafetyGateCheck("MAX_DAILY_LOSS", not max_daily_loss_exceeded,
                            "Max daily loss exceeded"),
            SafetyGateCheck("MAX_POSITION", not max_position_exceeded,
                            "Max position limit exceeded"),
            SafetyGateCheck("DUPLICATE_ORDER", not duplicate_order,
                            "Duplicate order detected"),
            SafetyGateCheck("WS_CONNECTED", ws_connected,
                            "WebSocket disconnected — risk too high"),
        ]

        passed = all(c.passed for c in checks)
        block_reasons = [c.reason for c in checks if not c.passed]

        return SafetyGateResult(
            passed=passed,
            checks=checks,
            block_reasons=block_reasons,
        )
