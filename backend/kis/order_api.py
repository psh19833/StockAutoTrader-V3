"""KIS Live Order API — guarded order submission (N14).

Order endpoints are blocked by SafetyGate and LIVE_TRADING_ENABLED.
All methods require SafetyGate approval before calling KIS.
"""
from __future__ import annotations

from typing import Optional, Protocol

BUY_TR_ID = "TTTC0012U"
SELL_TR_ID = "TTTC0011U"


class OrderSubmitResult:
    def __init__(
        self,
        success: bool,
        order_number: str = "",
        message: str = "",
        error_type: str = "",
    ):
        self.success = success
        self.order_number = order_number
        self.message = message
        self.error_type = error_type


class CashOrderSubmitter(Protocol):
    """Order submitter interface.

    Production submitter may call KIS HTTP.
    Unit tests must use an explicit fake/stub.
    """

    def submit_cash_order(self, payload: dict, tr_id: str) -> "OrderSubmitResult": ...


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
    submitter: Optional[CashOrderSubmitter] = None,
) -> OrderSubmitResult:
    """Submit KIS cash order — requires SafetyGate and LIVE_TRADING_ENABLED.

    Returns OrderSubmitResult with success=False if blocked.
    """
    if not live_trading_enabled:
        return OrderSubmitResult(
            success=False,
            message="LIVE_TRADING_ENABLED=false — order blocked",
            error_type="LIVE_TRADING_DISABLED",
        )
    if not safety_gate_approved:
        return OrderSubmitResult(
            success=False,
            message="Safety gate not approved — order blocked",
            error_type="SAFETY_GATE_NOT_APPROVED",
        )

    # LIVE + SafetyGate approved 상태에서도, submitter가 주입되지 않았다면
    # 절대 success=True 를 반환하면 안 된다 (실전 주문 접수로 오인 위험).
    if submitter is None:
        return OrderSubmitResult(
            success=False,
            message="KIS live order submitter not configured — order not submitted",
            error_type="ORDER_SUBMITTER_NOT_CONFIGURED",
        )

    tr_id = BUY_TR_ID if side.upper() == "BUY" else SELL_TR_ID
    payload = build_cash_order_payload(
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        account_no=account_no,
    )
    # 실제 KIS 주문 HTTP 호출 구현은 이번 Phase에서 제공하지 않는다.
    # submitter 구현체에서만 네트워크 호출이 가능하다.
    return submitter.submit_cash_order(payload=payload, tr_id=tr_id)
