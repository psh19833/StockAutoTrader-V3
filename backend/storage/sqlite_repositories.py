"""SQLite Repository Implementations"""
import sqlite3
import json
from storage.serializers import sanitize_for_storage


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


class SqliteAuditEventRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _derive_status_summary(self, clean: dict) -> tuple[str, str, int]:
        """Derive status/summary/has_checklist from payload (best-effort)."""
        payload = clean.get("payload") if isinstance(clean.get("payload"), dict) else {}
        has_checklist = 1 if isinstance(payload.get("checklist"), dict) else 0

        status = str(clean.get("status", "") or "")
        summary = str(clean.get("summary", "") or "")

        if not summary:
            for k in ("reason_text", "reason_code", "excluded_reason"):
                if k in payload and payload.get(k):
                    summary = str(payload.get(k))
                    break

        if not status and has_checklist:
            items = payload.get("checklist", {}).get("items", [])
            worst = "INFO"
            for it in items if isinstance(items, list) else []:
                s = (it or {}).get("status")
                if s == "FAIL":
                    worst = "FAIL"; break
                if s == "WARN" and worst not in ("FAIL", "WARN"):
                    worst = "WARN"
                if s == "PASS" and worst == "INFO":
                    worst = "PASS"
            status = worst

        return status, summary, has_checklist

    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        status, summary, has_checklist = self._derive_status_summary(clean)

        # Ensure event_id/event_time exist (tests and legacy callers may omit them)
        event_id = str(clean.get("event_id", "") or "")
        if not event_id:
            import uuid
            event_id = uuid.uuid4().hex[:16]

        event_time = str(clean.get("event_time", "") or "")
        if not event_time:
            from datetime import datetime, timezone
            event_time = datetime.now(timezone.utc).isoformat()

        payload_obj = clean.get("payload", {})
        payload_json = (
            json.dumps(payload_obj) if isinstance(payload_obj, dict)
            else str(payload_obj or "{}")
        )

        cur = self._conn.execute(
            "INSERT INTO audit_events (event_id, event_time, event_type, correlation_id, symbol, "
            "severity, payload, source, strategy_name, status, summary, has_checklist) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                event_time,
                clean.get("event_type", ""),
                clean.get("correlation_id", ""),
                clean.get("symbol", ""),
                clean.get("severity", "INFO"),
                payload_json,
                clean.get("source", ""),
                clean.get("strategy_name", ""),
                status,
                summary,
                has_checklist,
            ),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def list_all(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events ORDER BY COALESCE(event_time, created_at) DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return _rows_to_list(rows)

    def get_by_event_id(self, event_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM audit_events WHERE event_id = ? LIMIT 1",
            (event_id,),
        ).fetchone()
        return _row_to_dict(row)

    def find_by_correlation(self, correlation_id: str, limit: int = 200) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events WHERE correlation_id = ? "
            "ORDER BY COALESCE(event_time, created_at) ASC, id ASC LIMIT ?",
            (correlation_id, limit)
        ).fetchall()
        return _rows_to_list(rows)


class SqliteScannerCandidateRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO scanner_candidates "
            "(scan_run_id, symbol, scanner_type, included, excluded_reason, metrics_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (clean.get("scan_run_id", ""), clean.get("symbol", ""),
             clean.get("scanner_type", ""), 1 if clean.get("included") else 0,
             clean.get("excluded_reason"), json.dumps(clean.get("metrics_json", {}))),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def list_by_scan(self, scan_run_id: str) -> list[dict]:
        return _rows_to_list(self._conn.execute(
            "SELECT * FROM scanner_candidates WHERE scan_run_id = ?",
            (scan_run_id,)
        ).fetchall())

    def list_included(self, scan_run_id: str) -> list[dict]:
        return _rows_to_list(self._conn.execute(
            "SELECT * FROM scanner_candidates WHERE scan_run_id = ? AND included = 1",
            (scan_run_id,)
        ).fetchall())

    def list_excluded(self, scan_run_id: str) -> list[dict]:
        return _rows_to_list(self._conn.execute(
            "SELECT * FROM scanner_candidates WHERE scan_run_id = ? AND included = 0",
            (scan_run_id,)
        ).fetchall())


class SqliteQuantScoreRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO quant_scores (evaluation_id, symbol, scanner_type, decision, final_score) "
            "VALUES (?, ?, ?, ?, ?)",
            (clean.get("evaluation_id", ""), clean.get("symbol", ""),
             clean.get("scanner_type", ""), clean.get("decision", ""),
             clean.get("final_score", 0)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get(self, evaluation_id: str) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM quant_scores WHERE evaluation_id = ?", (evaluation_id,)
        ).fetchone())


class SqliteStrategySignalRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO strategy_signals (signal_id, correlation_id, symbol, side, strategy_type, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (clean.get("signal_id", ""), clean.get("correlation_id", ""),
             clean.get("symbol", ""), clean.get("side", ""),
             clean.get("strategy_type", ""), clean.get("confidence", 0)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get(self, signal_id: str) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM strategy_signals WHERE signal_id = ?", (signal_id,)
        ).fetchone())


class SqliteRiskDecisionRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO risk_decisions (risk_decision_id, signal_id, correlation_id, symbol, side, allowed, reason_code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clean.get("risk_decision_id", ""), clean.get("signal_id", ""),
             clean.get("correlation_id", ""), clean.get("symbol", ""),
             clean.get("side", ""), 1 if clean.get("allowed") else 0,
             clean.get("reason_code", "")),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get(self, risk_decision_id: str) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM risk_decisions WHERE risk_decision_id = ?", (risk_decision_id,)
        ).fetchone())


class SqliteOrderRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO orders (order_intent_id, risk_decision_id, symbol, side, status, quantity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (clean.get("order_intent_id", ""), clean.get("risk_decision_id", ""),
             clean.get("symbol", ""), clean.get("side", ""),
             clean.get("status", ""), clean.get("quantity", 0)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get(self, order_intent_id: str) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM orders WHERE order_intent_id = ?", (order_intent_id,)
        ).fetchone())


class SqliteFillRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO fills (fill_id, order_intent_id, symbol, side, filled_qty, filled_price, remaining_qty) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clean.get("fill_id", ""), clean.get("order_intent_id", ""),
             clean.get("symbol", ""), clean.get("side", ""),
             clean.get("filled_qty", 0), clean.get("filled_price", 0),
             clean.get("remaining_qty", 0)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get(self, fill_id: str) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM fills WHERE fill_id = ?", (fill_id,)
        ).fetchone())


class SqlitePortfolioSnapshotRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT INTO portfolio_snapshots (symbol, name, quantity, avg_buy_price, current_price, unrealized_pnl) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (clean.get("symbol", ""), clean.get("name", ""),
             clean.get("quantity", 0), clean.get("avg_buy_price", 0),
             clean.get("current_price", 0), clean.get("unrealized_pnl", 0)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def list_all(self) -> list[dict]:
        return _rows_to_list(self._conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY id DESC"
        ).fetchall())


class SqliteEodReportRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        import json
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO eod_reports (trading_date, total_pnl, total_realized_pnl, "
            "total_unrealized_pnl, win_rate, profit_factor, total_orders, fills, report_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (clean.get("trading_date", ""), clean.get("total_pnl", 0),
             clean.get("total_realized_pnl", 0), clean.get("total_unrealized_pnl", 0),
             clean.get("win_rate", 0), clean.get("profit_factor", 0),
             clean.get("total_orders", 0), clean.get("fills", 0),
             json.dumps(clean)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get_latest(self) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM eod_reports ORDER BY id DESC LIMIT 1"
        ).fetchone())


# Compatibility aliases with simple in-memory fallback
class SqliteScanRunRepository:
    def __init__(self, conn): self._conn = conn
    def save(self, data: dict) -> int:
        clean = sanitize_for_storage(data)
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO scan_runs (scan_run_id, scanner_type, market_regime, "
            "collected_count, included_count, excluded_count) VALUES (?, ?, ?, ?, ?, ?)",
            (clean.get("scan_run_id", ""), clean.get("scanner_type", ""),
             clean.get("market_regime", ""), clean.get("collected_count", 0),
             clean.get("included_count", 0), clean.get("excluded_count", 0)),
        )
        self._conn.commit()
        return cur.lastrowid or 0
    def get(self, scan_run_id: str) -> dict | None:
        return _row_to_dict(self._conn.execute(
            "SELECT * FROM scan_runs WHERE scan_run_id = ?", (scan_run_id,)
        ).fetchone())
