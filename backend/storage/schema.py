"""Database Schema — 테이블 정의"""
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    event_time TEXT,
    event_type TEXT NOT NULL,
    correlation_id TEXT,
    symbol TEXT,
    severity TEXT DEFAULT 'INFO',
    payload TEXT DEFAULT '{}',
    source TEXT DEFAULT '',
    strategy_name TEXT DEFAULT '',
    status TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    has_checklist INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_event_id ON audit_events(event_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_time ON audit_events(event_time);
CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id TEXT UNIQUE NOT NULL,
    scanner_type TEXT NOT NULL,
    market_regime TEXT,
    collected_count INTEGER DEFAULT 0,
    included_count INTEGER DEFAULT 0,
    excluded_count INTEGER DEFAULT 0,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scanner_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    scanner_type TEXT NOT NULL,
    included INTEGER DEFAULT 1,
    excluded_reason TEXT,
    metrics_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_candidates_scan ON scanner_candidates(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_candidates_symbol ON scanner_candidates(symbol);

CREATE TABLE IF NOT EXISTS quant_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    scanner_type TEXT,
    decision TEXT,
    final_score REAL,
    liquidity_score REAL DEFAULT 0,
    momentum_score REAL DEFAULT 0,
    market_regime_adjustment REAL DEFAULT 0,
    symbol_risk_penalty REAL DEFAULT 0,
    metrics_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_quant_symbol ON quant_scores(symbol);

CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE NOT NULL,
    correlation_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT,
    strategy_type TEXT,
    confidence REAL DEFAULT 0,
    market_regime TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_decision_id TEXT UNIQUE NOT NULL,
    signal_id TEXT,
    correlation_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT,
    allowed INTEGER DEFAULT 0,
    reason_code TEXT,
    reason_text TEXT,
    market_regime TEXT,
    session_state TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_intent_id TEXT UNIQUE NOT NULL,
    risk_decision_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT,
    status TEXT,
    quantity INTEGER DEFAULT 0,
    estimated_amount INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fill_id TEXT UNIQUE NOT NULL,
    order_intent_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT,
    filled_qty INTEGER DEFAULT 0,
    filled_price INTEGER DEFAULT 0,
    remaining_qty INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    quantity INTEGER DEFAULT 0,
    avg_buy_price INTEGER DEFAULT 0,
    current_price INTEGER DEFAULT 0,
    unrealized_pnl INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS eod_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_date TEXT UNIQUE NOT NULL,
    total_pnl INTEGER DEFAULT 0,
    total_realized_pnl INTEGER DEFAULT 0,
    total_unrealized_pnl INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    profit_factor REAL DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    fills INTEGER DEFAULT 0,
    report_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
"""
