from __future__ import annotations

from audit_logging.audit_event import AuditEvent, AuditEventType
from notifications.telegram_formatter import format_audit_event
from order.fill_reconciliation import FillReconciler
from order.order_intent import OrderIntent
from order.order_submitter import SafeStubSubmitter
from order.order_types import OrderSide, OrderType
from portfolio.portfolio_sync import PortfolioSync
from portfolio.position import PositionSnapshot
from runtime.dry_decision_runner import DryDecisionRunner
from safety.live_order_safety_gate import LiveOrderSafetyGate


def test_full_live_chain_mock_e2e_single_tick_without_real_kis_order() -> None:
    # 1) Scanner -> Quant -> Strategy -> Risk in one tick (dry pipeline artifact)
    dry = DryDecisionRunner().run(symbols=["005930"])
    assert len(dry["candidates"]) >= 1
    assert dry["scores"][0]["decision"] == "PASS"
    assert len(dry["signals"]) >= 1
    assert dry["risk_decisions"][0]["allowed"] is True

    # 2) SafetyGate pass
    gate = LiveOrderSafetyGate()
    gate_result = gate.check(
        live_trading_enabled=True,
        session="REGULAR_MARKET",
        market_regime="BULL",
        risk_approved=True,
        quote_stale=False,
        orderbook_stale=False,
        max_daily_loss_exceeded=False,
        duplicate_order=False,
        ws_connected=True,
    )
    assert gate_result.passed is True

    # 3) OrderIntent 생성 -> Mock submitter ORDER_SUBMITTED
    corr_id = "corr-e2e-001"
    intent = OrderIntent(
        order_intent_id="intent-001",
        risk_decision_id="risk-001",
        signal_id="sig-001",
        correlation_id=corr_id,
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=100,
        estimated_amount=100,
        source_strategy="RAPID_SURGE",
        live_trading_enabled_snapshot=True,
        approved_by_risk=True,
    )
    submit_result = SafeStubSubmitter(should_fail=False).submit(intent)
    assert submit_result.status.value == "ORDER_SUBMITTED"

    # 4) Fill 3-way reconciliation (WS + REST fill + REST balance)
    reconciler = FillReconciler()
    order_no = "ord-e2e-001"
    reconciler.on_ws_fill_notice("005930", order_no, fill_price=100, fill_volume=1)
    assert reconciler.is_confirmed(order_no) is False

    # confirmed 전에는 portfolio final 반영 금지
    pf = PortfolioSync()
    if not reconciler.is_confirmed(order_no):
        pf.mark_stale("fill_not_confirmed")
    assert pf.stale is True
    assert "fill_not_confirmed" in pf.mismatch_reasons

    reconciler.on_rest_fill_check(order_no, confirmed=True, rest_fill_price=100, rest_fill_volume=1)
    assert reconciler.is_confirmed(order_no) is False
    reconciler.on_rest_balance_check(order_no, reflected=True)
    assert reconciler.is_confirmed(order_no) is True

    # 5) Portfolio sync 최종 반영
    pos = PositionSnapshot(
        symbol="005930",
        name="삼성전자",
        quantity=1,
        avg_buy_price=100,
        current_price=100,
    )
    pf.update_snapshot((pos,), total_realized_pnl=0, total_unrealized_pnl=0, source_of_truth="KIS_REST", stale=False)
    assert pf.stale is False
    assert pf.source_of_truth == "KIS_REST"
    assert len(pf.positions) == 1

    # 6) Audit correlation_id 연결 + Telegram 의미 분리 검증
    order_event = AuditEvent(
        event_type=AuditEventType.ORDER_SUBMITTED.value,
        correlation_id=corr_id,
        symbol="005930",
        payload={"order_type": "LIMIT", "quantity": 1, "price": 100},
    )
    fill_event = AuditEvent(
        event_type=AuditEventType.FILL_CONFIRMED.value,
        correlation_id=corr_id,
        symbol="005930",
        payload={"order_type": "LIMIT", "filled_quantity": 1, "filled_price": 100},
    )
    t_order = format_audit_event(order_event)
    t_fill = format_audit_event(fill_event)

    assert order_event.correlation_id == fill_event.correlation_id == corr_id
    assert "체결 아님" in t_order.title or "체결 아님" in t_order.body
    assert "체결 완료" in t_fill.title
    assert "체결되었습니다" in t_fill.body
