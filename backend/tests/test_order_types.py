"""Tests for Order Types"""
from __future__ import annotations

from order.order_types import OrderType, OrderSide


class TestOrderType:
    def test_has_market(self):
        assert OrderType.MARKET.value == "MARKET"

    def test_has_limit(self):
        assert OrderType.LIMIT.value == "LIMIT"


class TestOrderSide:
    def test_buy(self):
        assert OrderSide.BUY.value == "BUY"

    def test_sell(self):
        assert OrderSide.SELL.value == "SELL"
