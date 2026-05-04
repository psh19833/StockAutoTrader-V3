"""Tests for SAT3-N5: Database Storage Foundation"""
from __future__ import annotations

import pytest
import sqlite3
import os
from pathlib import Path

from storage.database import get_connection, init_db, reset_db
from storage.repositories import (
    AuditEventRepository, ScanRunRepository,
    ScannerCandidateRepository, QuantScoreRepository,
    StrategySignalRepository, RiskDecisionRepository,
    OrderRepository, FillRepository,
    PortfolioSnapshotRepository, EodReportRepository,
)
from storage.sqlite_repositories import (
    SqliteAuditEventRepository, SqliteScanRunRepository,
    SqliteScannerCandidateRepository, SqliteQuantScoreRepository,
    SqliteStrategySignalRepository, SqliteRiskDecisionRepository,
    SqliteOrderRepository, SqliteFillRepository,
    SqlitePortfolioSnapshotRepository, SqliteEodReportRepository,
)
from storage.serializers import sanitize_for_storage


@pytest.fixture(autouse=True)
def _setup_db():
    """각 테스트 전에 InMemory DB 초기화"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield
    conn.close()


class TestDatabaseInit:
    def test_tables_created(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        expected = {
            "audit_events", "scan_runs", "scanner_candidates",
            "quant_scores", "strategy_signals", "risk_decisions",
            "orders", "fills", "portfolio_snapshots", "eod_reports",
        }
        assert expected <= table_names
        conn.close()


class TestSerializers:
    def test_sanitize_removes_secrets(self):
        data = {
            "symbol": "005930",
            "app_key": "PSH1234567890",
            "api_secret": "my_secret",
            "token": "bearer_abc123",
            "account_no": "44413716-01",
            "chat_id": "12345678",
            "price": 75000,
        }
        clean = sanitize_for_storage(data)
        assert clean["symbol"] == "005930"
        assert clean["price"] == 75000
        assert "app_key" not in clean
        assert "api_secret" not in clean
        assert "token" not in clean
        assert "account_no" not in clean
        assert "chat_id" not in clean

    def test_sanitize_handles_nested(self):
        data = {"payload": {"token": "secret", "value": 42}}
        clean = sanitize_for_storage(data)
        assert clean["payload"]["value"] == 42
        assert "token" not in clean["payload"]


class TestAuditEventRepository:
    def test_save_and_list(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        repo = SqliteAuditEventRepository(conn)

        repo.save({
            "event_type": "SCAN_STARTED", "correlation_id": "corr_001",
            "symbol": "005930", "severity": "INFO",
            "payload": '{"scanner_type": "RAPID_SURGE"}',
        })
        repo.save({
            "event_type": "QUANT_EVALUATED", "correlation_id": "corr_001",
            "symbol": "005930", "severity": "INFO",
            "payload": '{"decision": "PASS"}',
        })

        events = repo.list_all(limit=10)
        assert len(events) == 2

    def test_find_by_correlation(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        repo = SqliteAuditEventRepository(conn)

        repo.save({"event_type": "A", "correlation_id": "corr_A",
                    "symbol": "", "severity": "INFO", "payload": "{}"})
        repo.save({"event_type": "B", "correlation_id": "corr_B",
                    "symbol": "", "severity": "INFO", "payload": "{}"})

        results = repo.find_by_correlation("corr_A")
        assert len(results) == 1
        assert results[0]["event_type"] == "A"


class TestScannerCandidateRepository:
    def test_save_and_get(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        repo = SqliteScannerCandidateRepository(conn)

        repo.save({
            "scan_run_id": "scan_001", "symbol": "005930",
            "scanner_type": "RAPID_SURGE", "included": True,
            "excluded_reason": None, "metrics_json": "{}",
        })
        repo.save({
            "scan_run_id": "scan_001", "symbol": "999999",
            "scanner_type": "RAPID_SURGE", "included": False,
            "excluded_reason": "ETF_EXCLUDED", "metrics_json": "{}",
        })

        all_candidates = repo.list_by_scan("scan_001")
        assert len(all_candidates) == 2
        included = repo.list_included("scan_001")
        assert len(included) == 1
        excluded = repo.list_excluded("scan_001")
        assert len(excluded) == 1
        assert excluded[0]["excluded_reason"] == "ETF_EXCLUDED"
        conn.close()


class TestDashboardServiceWithRepository:
    def test_dashboard_service_accepts_repository(self):
        """DashboardService가 repository 주입 구조를 수용하는지"""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)

        from dashboard.dashboard_service import DashboardService
        svc = DashboardService()
        svc.set_audit_repository(SqliteAuditEventRepository(conn))
        assert svc._audit_repo is not None
        conn.close()
