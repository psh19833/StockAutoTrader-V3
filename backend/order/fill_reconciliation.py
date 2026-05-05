"""Fill and Position Reconciliation (N15).

주문 접수 ≠ 체결 성공.
체결 확정 = WS fill notice (provisional) + REST fills 조회 + REST balance 조회.

Three-way reconciliation before confirming any fill.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FillRecord:
    symbol: str
    order_number: str
    fill_price: int = 0
    fill_volume: int = 0
    status: str = "PENDING"
    source: str = ""


class FillReconciler:
    """Three-way fill reconciliation."""

    def __init__(self):
        self._ws_fills: dict[str, FillRecord] = {}
        self._rest_fills: dict[str, FillRecord] = {}
        self._balance_confirmed: dict[str, bool] = {}
        self._confirmed_fills: dict[str, FillRecord] = {}

    def on_ws_fill_notice(self, symbol: str, order_number: str,
                          fill_price: int, fill_volume: int) -> None:
        """Receive provisional fill from WebSocket."""
        self._ws_fills[order_number] = FillRecord(
            symbol=symbol, order_number=order_number,
            fill_price=fill_price, fill_volume=fill_volume,
            status="PROVISIONAL", source="KIS_API_WS",
        )

    def on_rest_fill_check(self, order_number: str, confirmed: bool) -> None:
        """Confirm fill via REST fills API.

        Note: REST fill confirmation alone is NOT enough.
        We require balance/position snapshot confirmation too.
        """
        if order_number not in self._ws_fills:
            return
        record = self._ws_fills[order_number]
        if confirmed:
            record.status = "REST_FILL_CONFIRMED"
            self._rest_fills[order_number] = record
        self._try_finalize(order_number)

    def on_rest_balance_check(self, order_number: str, reflected: bool) -> None:
        """Confirm fill via REST balance/position snapshot.

        reflected=True means the position/balance snapshot reflects the fill.
        """
        self._balance_confirmed[order_number] = bool(reflected)
        self._try_finalize(order_number)

    def _try_finalize(self, order_number: str) -> None:
        ws_ok = order_number in self._ws_fills
        rest_ok = order_number in self._rest_fills
        bal_ok = self._balance_confirmed.get(order_number) is True

        if ws_ok and rest_ok and bal_ok:
            record = self._ws_fills[order_number]
            record.status = "CONFIRMED"
            self._confirmed_fills[order_number] = record
            return

        if ws_ok and rest_ok and not bal_ok:
            # Keep an explicit non-confirmed status until balance confirms.
            self._ws_fills[order_number].status = "PENDING_BALANCE_CONFIRMATION"

    def is_confirmed(self, order_number: str) -> bool:
        return order_number in self._confirmed_fills

    def get_fill(self, order_number: str) -> Optional[FillRecord]:
        return self._confirmed_fills.get(order_number) or self._ws_fills.get(order_number)
