"""Order Types — 주문 타입 enum"""
from __future__ import annotations
from enum import Enum

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
