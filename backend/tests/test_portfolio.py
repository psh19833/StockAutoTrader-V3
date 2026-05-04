"""Tests for Portfolio — Position, PnL, PortfolioSync"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from portfolio.position import PositionSnapshot
from portfolio.pnl import compute_realized_pnl, compute_unrealized_pnl
from portfolio.portfolio_sync import PortfolioSync
from portfolio.portfolio_audit import build_portfolio_audit_event


class TestPositionSnapshot:
    def test_create_position(self):
        pos = PositionSnapshot(
            symbol="005930", name="삼성전자", quantity=10,
            avg_buy_price=74000, current_price=75000,
        )
        assert pos.symbol == "005930"
        assert pos.quantity == 10
        assert pos.avg_buy_price == 74000

    def test_position_frozen(self):
        pos = PositionSnapshot(
            symbol="005930", name="삼성전자", quantity=10,
            avg_buy_price=74000, current_price=75000,
        )
        with pytest.raises(Exception):
            pos.quantity = 20  # type: ignore

    def test_created_at_default(self):
        pos = PositionSnapshot(
            symbol="005930", name="삼성전자", quantity=10,
            avg_buy_price=74000, current_price=75000,
        )
        now = datetime.now(timezone.utc)
        assert abs((now - pos.created_at).seconds) < 10


class TestComputePnl:
    def test_realized_pnl_profit(self):
        pnl = compute_realized_pnl(
            buy_price=74000, sell_price=75000, quantity=10
        )
        assert pnl > 0
        assert pnl == 10000  # (75000-74000)*10

    def test_realized_pnl_loss(self):
        pnl = compute_realized_pnl(
            buy_price=75000, sell_price=74000, quantity=10
        )
        assert pnl < 0

    def test_unrealized_pnl_profit(self):
        pnl = compute_unrealized_pnl(
            avg_buy_price=74000, current_price=75000, quantity=10
        )
        assert pnl > 0

    def test_unrealized_pnl_loss(self):
        pnl = compute_unrealized_pnl(
            avg_buy_price=75000, current_price=74000, quantity=10
        )
        assert pnl < 0

    def test_realized_vs_unrealized_separate(self):
        """실현손익과 평가손익은 분리되어야 한다"""
        real = compute_realized_pnl(74000, 75000, 10)
        unreal = compute_unrealized_pnl(75000, 78000, 10)
        assert isinstance(real, int)
        assert isinstance(unreal, int)
        assert real != unreal


class TestPortfolioSync:
    def test_no_fake_balance(self):
        """PortfolioSync는 가짜 잔고를 만들지 않는다"""
        ps = PortfolioSync()
        assert ps.positions == ()
        assert ps.total_realized_pnl == 0
        assert ps.total_unrealized_pnl == 0

    def test_add_position(self):
        ps = PortfolioSync()
        pos = PositionSnapshot(
            symbol="005930", name="삼성전자", quantity=10,
            avg_buy_price=74000, current_price=75000,
        )
        ps.add_position(pos)
        assert len(ps.positions) == 1
        assert ps.positions[0].symbol == "005930"

    def test_update_snapshot(self):
        ps = PortfolioSync()
        ps.update_snapshot(
            positions=(), total_realized_pnl=50000,
            total_unrealized_pnl=30000,
        )
        assert ps.total_realized_pnl == 50000
        assert ps.total_unrealized_pnl == 30000


class TestPortfolioAudit:
    def test_audit_event(self):
        event = build_portfolio_audit_event(
            event_type="PORTFOLIO_SNAPSHOT",
            total_realized=50000,
            total_unrealized=30000,
            position_count=1,
        )
        assert event.event_type == "PORTFOLIO_SNAPSHOT"
        assert event.payload["position_count"] == 1

    def test_no_secret_leak(self):
        event = build_portfolio_audit_event(
            event_type="PORTFOLIO_SNAPSHOT",
            total_realized=50000, total_unrealized=30000,
            position_count=1,
        )
        for secret in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert secret not in str(event.payload)
