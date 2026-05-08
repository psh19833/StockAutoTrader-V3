"""KIS Live Order API — guarded order submission (N14)."""
from __future__ import annotations

import re
import os
from typing import Optional, Protocol

from safety.live_order_safety_gate import SafetyGateResult
from kis.token_provider import KisTokenProvider

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
    def submit_cash_order(self, payload: dict, tr_id: str) -> "OrderSubmitResult": ...


class GuardedKisCashOrderSubmitter:
    """Guarded submitter using token provider and explicit order transport call path."""

    def __init__(self, *, transport, token_provider: KisTokenProvider, app_key: str, app_secret: str):
        self._transport = transport
        self._token_provider = token_provider
        self._app_key = app_key
        self._app_secret = app_secret

    def submit_cash_order(self, payload: dict, tr_id: str) -> OrderSubmitResult:
        token = self._token_provider.issue_token()
        headers = {
            "authorization": f"{token.token_type} {token.access_token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "content-type": "application/json",
        }
        resp = self._transport.post_json(
            "/uapi/domestic-stock/v1/trading/order-cash",
            json_data=payload,
            headers=headers,
        )
        body = resp.body if isinstance(resp.body, dict) else {}
        ok = str(body.get("rt_cd", "")) == "0"
        order_no = str(body.get("output", {}).get("ODNO", "") if isinstance(body.get("output", {}), dict) else "")
        if ok:
            return OrderSubmitResult(True, order_number=order_no, message="ORDER_SUBMITTED", error_type="")
        msg_cd = str(body.get("msg_cd", body.get("error_code", "")))
        msg1 = str(body.get("msg1", body.get("error_description", "")))
        return OrderSubmitResult(False, order_number="", message=f"ORDER_REJECTED:{msg_cd}:{msg1}", error_type="ORDER_REJECTED")


def build_cash_order_payload(
    symbol: str,
    side: str,
    qty: int,
    price: int = 0,
    account_no: str = "",
    account_product_code: str = "01",
) -> dict:
    return {
        "CANO": account_no.replace("-", "")[:8] if account_no else "",
        "ACNT_PRDT_CD": account_product_code,
        "PDNO": symbol,
        "ORD_DVSN": "00",
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
    account_product_code: str = "01",
    safety_gate_approved: bool = False,
    safety_gate_result: Optional[SafetyGateResult] = None,
    live_trading_enabled: bool = False,
    risk_decision_approved: bool = False,
    correlation_id: str = "",
    strict_validation: bool = True,
    submitter: Optional[CashOrderSubmitter] = None,
) -> OrderSubmitResult:
    side = (side or "").upper()
    if side not in ("BUY", "SELL"):
        return OrderSubmitResult(False, message="Invalid side", error_type="INVALID_SIDE")
    if not re.fullmatch(r"\d{6}", symbol or ""):
        return OrderSubmitResult(False, message="Invalid symbol", error_type="INVALID_SYMBOL")
    if qty <= 0:
        return OrderSubmitResult(False, message="Invalid qty", error_type="INVALID_QTY")
    if price < 0:
        return OrderSubmitResult(False, message="Invalid price", error_type="INVALID_PRICE")
    if not live_trading_enabled:
        return OrderSubmitResult(False, message="LIVE_TRADING_ENABLED=false — order blocked", error_type="LIVE_TRADING_DISABLED")
    strict_required = bool(live_trading_enabled)
    strict_active = bool(strict_validation or strict_required)
    if safety_gate_result is None:
        return OrderSubmitResult(False, message="Safety gate result is required — order blocked", error_type="SAFETY_GATE_CHAIN_REQUIRED")
    if not safety_gate_result.passed:
        reasons = ", ".join(safety_gate_result.block_reasons) if safety_gate_result.block_reasons else "unknown"
        return OrderSubmitResult(False, message=f"Safety gate blocked order: {reasons}", error_type="SAFETY_GATE_NOT_APPROVED")
    if not safety_gate_approved:
        return OrderSubmitResult(False, message="Safety gate approved flag is false — order blocked", error_type="SAFETY_GATE_NOT_APPROVED")
    if strict_active and not risk_decision_approved:
        return OrderSubmitResult(False, message="Risk decision not approved - order blocked", error_type="RISK_NOT_APPROVED")
    if strict_active and not account_no:
        return OrderSubmitResult(False, message="Missing account_no", error_type="ACCOUNT_REQUIRED")
    if strict_active and not account_product_code:
        return OrderSubmitResult(False, message="Missing account product code", error_type="ACCOUNT_PRODUCT_REQUIRED")
    configured_account_no = str(os.getenv("KIS_ACCOUNT_NO", "") or "").strip()
    if strict_active and configured_account_no and account_no.strip() != configured_account_no:
        return OrderSubmitResult(False, message="account_no does not match configured account", error_type="ACCOUNT_MISMATCH")
    if strict_active and not correlation_id:
        return OrderSubmitResult(False, message="Missing correlation_id", error_type="CORRELATION_ID_REQUIRED")
    if submitter is None:
        return OrderSubmitResult(False, message="KIS live order submitter not configured — order not submitted", error_type="ORDER_SUBMITTER_NOT_CONFIGURED")

    tr_id = BUY_TR_ID if side == "BUY" else SELL_TR_ID
    payload = build_cash_order_payload(
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        account_no=account_no,
        account_product_code=account_product_code,
    )
    return submitter.submit_cash_order(payload=payload, tr_id=tr_id)
