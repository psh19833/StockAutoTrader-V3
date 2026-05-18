from __future__ import annotations

import pytest

from kis.order_api import build_cash_order_payload


def test_build_payload_limit_sets_ord_dvsn_00_and_price() -> None:
    p = build_cash_order_payload(symbol="005930", side="BUY", qty=1, price=70000, order_type="LIMIT")
    assert p["ORD_DVSN"] == "00"
    assert p["ORD_UNPR"] == "70000"


def test_build_payload_market_sets_ord_dvsn_01_and_unpr_0_even_if_price_provided() -> None:
    p = build_cash_order_payload(symbol="005930", side="BUY", qty=1, price=70000, order_type="MARKET")
    assert p["ORD_DVSN"] == "01"
    assert p["ORD_UNPR"] == "0"


def test_build_payload_invalid_order_type_raises() -> None:
    with pytest.raises(ValueError):
        build_cash_order_payload(symbol="005930", side="BUY", qty=1, price=70000, order_type="STOP")
