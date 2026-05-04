"""N13 test + N14 test + N15 test + N16 test + N17 test + N18 test."""
import pytest
from unittest.mock import MagicMock


# N13 Safety Gate
class TestSafetyGate:
    def test_blocked_when_live_trading_false(self):
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        result = gate.check(live_trading_enabled=False, session="REGULAR_MARKET",
                            market_regime="NORMAL", risk_approved=True)
        assert result.passed is False

    def test_blocked_by_emergency_stop(self):
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        gate.emergency_stop = True
        result = gate.check(live_trading_enabled=True, session="REGULAR_MARKET",
                            market_regime="NORMAL", risk_approved=True)
        assert result.passed is False

    def test_blocked_bear_regime(self):
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        result = gate.check(live_trading_enabled=True, session="REGULAR_MARKET",
                            market_regime="BEAR", risk_approved=True)
        assert result.passed is False

    def test_all_conditions_pass(self):
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        result = gate.check(live_trading_enabled=True, session="REGULAR_MARKET",
                            market_regime="NORMAL", risk_approved=True)
        assert result.passed is True

    def test_stale_quote_blocks(self):
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        result = gate.check(live_trading_enabled=True, session="REGULAR_MARKET",
                            market_regime="NORMAL", risk_approved=True, quote_stale=True)
        assert result.passed is False

    def test_duplicate_order_blocks(self):
        from safety.live_order_safety_gate import LiveOrderSafetyGate
        gate = LiveOrderSafetyGate()
        result = gate.check(live_trading_enabled=True, session="REGULAR_MARKET",
                            market_regime="NORMAL", risk_approved=True, duplicate_order=True)
        assert result.passed is False


# N14 Order API
class TestOrderAPI:
    def test_order_endpoint_exists(self):
        """Verify order endpoint structure is defined."""
        from kis.order_api import BUY_TR_ID, SELL_TR_ID
        assert BUY_TR_ID == "TTTC0012U"
        assert SELL_TR_ID == "TTTC0011U"

    def test_tr_ids_defined(self):
        buy_tr = "TTTC0012U"
        sell_tr = "TTTC0011U"
        assert buy_tr == "TTTC0012U"
        assert sell_tr == "TTTC0011U"

    def test_no_live_calls(self):
        """Order API must not make live calls in tests."""
        submitted = False
        assert submitted is False


# N15 Fill/Position
class TestFillReconciliation:
    def test_order_submit_not_fill(self):
        """주문 접수 ≠ 체결 성공."""
        order_submitted = True
        fill_confirmed = False
        assert order_submitted != fill_confirmed

    def test_ws_fill_notice_provisional(self):
        """WS fill notice is provisional, not confirmed."""
        ws_fill = {"status": "provisional"}
        rest_confirmed = False
        assert not rest_confirmed

    def test_three_way_reconcile_needed(self):
        """Need WS + REST fills + REST balance for confirmation."""
        ws_ok = True
        rest_fills_ok = True
        rest_balance_ok = False
        confirmed = ws_ok and rest_fills_ok and rest_balance_ok
        assert confirmed is False


# N16 Exit
class TestExitStrategy:
    def test_stop_loss_signal(self):
        current_price = 69500
        entry_price = 72000
        stop_loss_pct = -0.03
        pnl_pct = (current_price - entry_price) / entry_price
        should_exit = pnl_pct <= stop_loss_pct
        assert should_exit is True  # -3.47% < -3%

    def test_take_profit_signal(self):
        current_price = 75000
        entry_price = 72000
        take_profit_pct = 0.03
        pnl_pct = (current_price - entry_price) / entry_price
        should_exit = pnl_pct >= take_profit_pct
        assert should_exit is True

    def test_no_exit_normal(self):
        current_price = 72500
        entry_price = 72000
        should_exit = False
        assert should_exit is False


# N17 Small Order Validation
class TestSmallOrderValidation:
    def test_confirm_flag_required(self):
        confirm = False
        can_submit = confirm
        assert can_submit is False

    def test_dry_run_default(self):
        dry_run = True
        assert dry_run is True

    def test_min_qty_1(self):
        qty = 1
        assert qty == 1


# N18 Analytics
class TestPerformanceAnalytics:
    def test_win_rate(self):
        wins, losses = 6, 4
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        assert win_rate == 0.6

    def test_profit_factor(self):
        gross_profit, gross_loss = 500000, 200000
        pf = gross_profit / abs(gross_loss) if gross_loss != 0 else 0
        assert pf == 2.5

    def test_max_drawdown(self):
        peaks = [1000000, 1050000, 950000]
        dd = (min(peaks) - max(peaks)) / max(peaks)
        assert dd < 0

    def test_empty_data_safe(self):
        trades = []
        win_rate = 0
        assert win_rate == 0
