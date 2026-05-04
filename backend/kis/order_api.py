"""KIS Live Order API — guarded order submission (N14).

Order endpoints are blocked by SafetyGate and LIVE_TRADING_ENABLED.
All methods require SafetyGate approval before calling KIS.
"""
from __future__ import annotations

from typing import Optional

BUY_TR_ID = "TTTC0012U"
SELL_TR_ID = "TTTC0011U"


class OrderSubmitResult:
    def __init__(self, success: bool, order_number: str = "", message: str = ""):
        self.success = success
        self.order_number = order_number
        self.message = message


def build_cash_order_payload(
    symbol: str,
    side: str,
    qty: int,
    price: int = 0,
    account_no: str = "",
) -> dict:
    """Build KIS cash order payload with uppercase keys per KIS spec."""
    tr_id = BUY_TR_ID if side.upper() == "BUY" else SELL_TR_ID
    return {
        "CANO": account_no.replace("-", "")[:8] if account_no else "",
        "ACNT_PRDT_CD": "01",
        "PDNO": symbol,
        "ORD_DVSN": "00",  # 지정가
        "ORD_QTY": str(qty),
        "ORD_UNPR": str(price) if price > 0 else "0",
        "CTAC_TLNO": "",
    }


def submit_cash_order(
    symbol: str,
    side: str,
    qty: int,
    price: int = 0,
    account_no: str = "",
    safety_gate_approved: bool = False,
    live_trading_enabled: bool = False,
) -> OrderSubmitResult:
    """Submit KIS cash order — requires SafetyGate and LIVE_TRADING_ENABLED.

    Returns OrderSubmitResult with success=False if blocked.
    """
    if not live_trading_enabled:
        return OrderSubmitResult(
            success=False,
            message="LIVE_TRADING_ENABLED=false — order blocked",
        )
    if not safety_gate_approved:
        return OrderSubmitResult(
            success=False,
            message="Safety gate not approved — order blocked",
        )
    # 실제 KIS 호출은 LIVE_TRADING_ENABLED=true + SafetyGate 통과 후에만
    return OrderSubmitResult(
        success=True,
        order_number="MOCK-ORDER-000",
        message="Order would be submitted (mock)",
    )
