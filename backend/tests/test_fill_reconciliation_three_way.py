from __future__ import annotations

from order.fill_reconciliation import FillReconciler


def test_ws_only_not_confirmed():
    r = FillReconciler()
    r.on_ws_fill_notice(symbol="005930", order_number="ord1", fill_price=100, fill_volume=1)
    assert r.is_confirmed("ord1") is False


def test_ws_plus_rest_fill_not_confirmed_until_balance():
    r = FillReconciler()
    r.on_ws_fill_notice(symbol="005930", order_number="ord1", fill_price=100, fill_volume=1)
    r.on_rest_fill_check(order_number="ord1", confirmed=True, rest_fill_price=100, rest_fill_volume=1)
    assert r.is_confirmed("ord1") is False
    rec = r.get_fill("ord1")
    assert rec is not None
    assert rec.status in ("REST_FILL_CONFIRMED", "PENDING_BALANCE_CONFIRMATION")


def test_three_way_confirmed_only_after_balance_reflects():
    r = FillReconciler()
    r.on_ws_fill_notice(symbol="005930", order_number="ord1", fill_price=100, fill_volume=1)
    r.on_rest_fill_check(order_number="ord1", confirmed=True, rest_fill_price=100, rest_fill_volume=1)
    r.on_rest_balance_check(order_number="ord1", reflected=True)
    assert r.is_confirmed("ord1") is True
    rec = r.get_fill("ord1")
    assert rec is not None
    assert rec.status == "CONFIRMED"


def test_balance_mismatch_keeps_unconfirmed():
    r = FillReconciler()
    r.on_ws_fill_notice(symbol="005930", order_number="ord1", fill_price=100, fill_volume=1)
    r.on_rest_fill_check(order_number="ord1", confirmed=True, rest_fill_price=100, rest_fill_volume=1)
    r.on_rest_balance_check(order_number="ord1", reflected=False)
    assert r.is_confirmed("ord1") is False


def test_rest_price_mismatch_keeps_unconfirmed_with_reason():
    r = FillReconciler()
    r.on_ws_fill_notice(symbol="005930", order_number="ord2", fill_price=100, fill_volume=1)
    r.on_rest_fill_check(order_number="ord2", confirmed=True, rest_fill_price=101, rest_fill_volume=1)
    assert r.is_confirmed("ord2") is False
    rec = r.get_fill("ord2")
    assert rec is not None
    assert rec.status == "MISMATCH"
    assert rec.mismatch_reason == "price_mismatch_ws_vs_rest"


def test_rest_volume_mismatch_keeps_unconfirmed_with_reason():
    r = FillReconciler()
    r.on_ws_fill_notice(symbol="005930", order_number="ord3", fill_price=100, fill_volume=2)
    r.on_rest_fill_check(order_number="ord3", confirmed=True, rest_fill_price=100, rest_fill_volume=1)
    assert r.is_confirmed("ord3") is False
    rec = r.get_fill("ord3")
    assert rec is not None
    assert rec.status == "MISMATCH"
    assert rec.mismatch_reason == "volume_mismatch_ws_vs_rest"
