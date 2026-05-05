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
    mismatch_reason: str = ""


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

    def on_rest_fill_check(
        self,
        order_number: str,
        confirmed: bool,
        rest_fill_price: int | None = None,
        rest_fill_volume: int | None = None,
    ) -> None:
        """Confirm fill via REST fills API.

        Note: REST fill confirmation alone is NOT enough.
        We require balance/position snapshot confirmation too.

        If REST fill quantity/price conflicts with WS provisional values,
        keep the record unconfirmed and persist mismatch reason.
        """
        if order_number not in self._ws_fills:
            return
        record = self._ws_fills[order_number]
        if not confirmed:
            record.status = "REST_FILL_NOT_CONFIRMED"
            record.mismatch_reason = "rest_fill_not_confirmed"
            self._try_finalize(order_number)
            return

        if rest_fill_price is not None and rest_fill_price != record.fill_price:
            record.status = "MISMATCH"
            record.mismatch_reason = "price_mismatch_ws_vs_rest"
            self._try_finalize(order_number)
            return

        if rest_fill_volume is not None and rest_fill_volume != record.fill_volume:
            record.status = "MISMATCH"
            record.mismatch_reason = "volume_mismatch_ws_vs_rest"
            self._try_finalize(order_number)
            return

        record.status = "REST_FILL_CONFIRMED"
        self._rest_fills[order_number] = record
        self._try_finalize(order_number)

    def on_rest_balance_check(self, order_number: str, reflected: bool) -> None:
        """Confirm fill via REST balance/position snapshot.

        reflected=True means the position/balance snapshot reflects the fill.
        """
        self._balance_confirmed[order_number] = bool(reflected)
        if order_number in self._ws_fills and not reflected:
            self._ws_fills[order_number].status = "BALANCE_MISMATCH"
            self._ws_fills[order_number].mismatch_reason = "balance_not_reflected"
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
