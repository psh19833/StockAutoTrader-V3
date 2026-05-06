"""KIS Live Order API — guarded order submission (N14).

Order endpoints are blocked by SafetyGate and LIVE_TRADING_ENABLED.
All methods require SafetyGate approval before calling KIS.
"""
from __future__ import annotations

from typing import Optional, Protocol
import os

from kis.transport import RealTransport
from safety.live_order_safety_gate import SafetyGateResult

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


class RealCashOrderSubmitter:
    """Real KIS cash-order submitter.

    Uses RealTransport with explicit order-endpoint allowance.
    Token is issued per submit call (simple/robust one-shot flow).
    """

    def __init__(self):
        self._app_key = os.getenv("KIS_APP_KEY", "")
        self._app_secret = os.getenv("KIS_APP_SECRET", "")
        self._base_url = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
        self._transport = RealTransport(base_url=self._base_url, timeout=30, allow_order_endpoints=True)

    def _issue_access_token(self) -> str:
        import urllib.request
        import json

        token_url = f"{self._base_url}/oauth2/tokenP"
        body = json.dumps({
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }).encode("utf-8")
        req = urllib.request.Request(token_url, data=body, method="POST")
        req.add_header("content-type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return str(data.get("access_token", ""))
        except Exception:
            return ""

    def submit_cash_order(self, payload: dict, tr_id: str) -> "OrderSubmitResult":
        access_token = self._issue_access_token()
        if not access_token:
            return OrderSubmitResult(False, "", "ACCESS_TOKEN_ISSUE_FAILED", "ACCESS_TOKEN_ISSUE_FAILED")

        headers = {
            "authorization": f"Bearer {access_token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "content-type": "application/json",
        }
        resp = self._transport.post_json("/uapi/domestic-stock/v1/trading/order-cash", payload, headers=headers)
        body = resp.body if isinstance(resp.body, dict) else {}

        ok = str(body.get("rt_cd", "")) == "0" and resp.status_code == 200
        if ok:
            out = body.get("output", {}) if isinstance(body.get("output"), dict) else {}
            order_no = str(out.get("ODNO", "") or out.get("odno", "") or body.get("odno", ""))
            return OrderSubmitResult(success=True, order_number=order_no, message="ORDER_SUBMITTED", error_type="")

        msg = str(body.get("msg1", body.get("error", "ORDER_SUBMIT_FAILED")))
        code = str(body.get("msg_cd", "ORDER_SUBMIT_FAILED"))
        return OrderSubmitResult(success=False, order_number="", message=msg, error_type=code)


def build_cash_order_payload(
    symbol: str,
    side: str,
    qty: int,
    price: int = 0,
    account_no: str = "",
) -> dict:
    """Build KIS cash order payload with uppercase keys per KIS spec."""
    tr_id = BUY_TR_ID if side.upper() == "BUY" else SELL_TR_ID
    ord_dvsn = "01" if price <= 0 else "00"
    return {
        "CANO": account_no.replace("-", "")[:8] if account_no else "",
        "ACNT_PRDT_CD": "01",
        "PDNO": symbol,
        "ORD_DVSN": ord_dvsn,  # 01 시장가, 00 지정가
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
    safety_gate_result: Optional[SafetyGateResult] = None,
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
    # SafetyGate 강제 체인:
    # bool 플래그만으로는 주문 경로를 허용하지 않는다.
    # 반드시 SafetyGateResult(체크 상세/차단 사유 포함)가 연결되어야 한다.
    if safety_gate_result is None:
        return OrderSubmitResult(
            success=False,
            message="Safety gate result is required — order blocked",
            error_type="SAFETY_GATE_CHAIN_REQUIRED",
        )

    if not safety_gate_result.passed:
        reasons = ", ".join(safety_gate_result.block_reasons) if safety_gate_result.block_reasons else "unknown"
        return OrderSubmitResult(
            success=False,
            message=f"Safety gate blocked order: {reasons}",
            error_type="SAFETY_GATE_NOT_APPROVED",
        )

    # 하위 호환: 명시적 false는 항상 차단
    if not safety_gate_approved:
        return OrderSubmitResult(
            success=False,
            message="Safety gate approved flag is false — order blocked",
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
