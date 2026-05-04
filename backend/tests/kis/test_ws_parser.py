"""Tests for backend/kis/ws_parser.py — KIS WebSocket raw message parser."""
import json
import hashlib
import pytest
from datetime import datetime, timezone

from kis.ws_parser import (
    WsMessageParser,
    dispatch_message,
    parse_trade_tick,
    parse_order_book,
    parse_fill_notice,
    parse_market_status,
    parse_expected_execution,
    compute_raw_hash,
)
from kis.ws_models import (
    RealtimeTradeTick,
    RealtimeOrderBook,
    RealtimeFillNotice,
    RealtimeMarketStatus,
    RealtimeExpectedExecution,
)


# ── raw_hash ─────────────────────────────────────────────────────────────────

class TestRawHash:
    def test_compute_raw_hash_consistent(self):
        raw = '{"tr_id":"H0STCNT0"}'
        h1 = compute_raw_hash(raw)
        h2 = compute_raw_hash(raw)
        assert h1 == h2

    def test_compute_raw_hash_different(self):
        h1 = compute_raw_hash('{"a":1}')
        h2 = compute_raw_hash('{"a":2}')
        assert h1 != h2

    def test_compute_raw_hash_is_sha256_hex(self):
        h = compute_raw_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ── parser: trade tick ───────────────────────────────────────────────────────

class TestParseTradeTick:
    def test_parse_valid(self):
        raw = json.dumps({
            "tr_id": "H0STCNT0",
            "MKSC_SHRN_ISCD": "005930",
            "STCK_CNTG_HOUR": "093015",
            "STCK_PRPR": "72000",
            "CNTG_VOL": "100",
            "STCK_OPRC": "71500",
            "STCK_HGPR": "72200",
            "STCK_LWPR": "71400",
            "STCK_BSOP_DATE": "20240501",
        })
        result = parse_trade_tick(raw)
        assert isinstance(result, RealtimeTradeTick)
        assert result.symbol == "005930"
        assert result.trade_price == 72000
        assert result.trade_volume == 100
        assert result.trade_time == "093015"
        assert result.parsed_ok is True
        assert result.source == "KIS_API_WS"

    def test_parse_has_raw_hash(self):
        raw = '{"tr_id":"H0STCNT0","MKSC_SHRN_ISCD":"005930"}'
        result = parse_trade_tick(raw)
        assert result.raw_hash is not None
        expected = compute_raw_hash(raw)
        assert result.raw_hash == expected

    def test_parse_missing_symbol(self):
        raw = '{"tr_id":"H0STCNT0"}'
        result = parse_trade_tick(raw)
        assert result.symbol == ""
        assert "symbol_missing" in result.data_quality_warnings


# ── parser: order book ───────────────────────────────────────────────────────

class TestParseOrderBook:
    def test_parse_valid(self):
        raw = json.dumps({
            "tr_id": "H0STASP0",
            "MKSC_SHRN_ISCD": "005930",
            "ASKP1": "72000", "ASKP2": "72050", "ASKP3": "72100",
            "BIDP1": "71900", "BIDP2": "71850", "BIDP3": "71800",
            "ASKP_RSQN1": "50", "ASKP_RSQN2": "30", "ASKP_RSQN3": "20",
            "BIDP_RSQN1": "40", "BIDP_RSQN2": "60", "BIDP_RSQN3": "10",
            "TOTAL_ASKP_RSQN": "100",
            "TOTAL_BIDP_RSQN": "110",
        })
        result = parse_order_book(raw)
        assert isinstance(result, RealtimeOrderBook)
        assert result.symbol == "005930"
        assert result.ask_prices == [72000, 72050, 72100]
        assert result.bid_prices == [71900, 71850, 71800]
        assert result.ask_volumes == [50, 30, 20]
        assert result.bid_volumes == [40, 60, 10]
        assert result.total_ask_volume == 100
        assert result.total_bid_volume == 110
        assert result.parsed_ok is True

    def test_parse_minimal(self):
        raw = json.dumps({"tr_id": "H0STASP0", "MKSC_SHRN_ISCD": "005930"})
        result = parse_order_book(raw)
        assert result.ask_prices == []
        assert result.parsed_ok is True


# ── parser: fill notice ──────────────────────────────────────────────────────

class TestParseFillNotice:
    def test_parse_valid(self):
        raw = json.dumps({
            "tr_id": "H0STCNI0",
            "MKSC_SHRN_ISCD": "005930",
            "ODNO": "ORD12345",
            "FTNG_ORD_PRC": "72000",
            "FTNG_ORD_QTY": "50",
            "CNTG_ISNM": "삼성전자",
        })
        result = parse_fill_notice(raw)
        assert isinstance(result, RealtimeFillNotice)
        assert result.symbol == "005930"
        assert result.order_number == "ORD12345"
        assert result.fill_price == 72000
        assert result.fill_volume == 50
        assert result.parsed_ok is True


# ── parser: market status ────────────────────────────────────────────────────

class TestParseMarketStatus:
    def test_parse_valid(self):
        raw = json.dumps({
            "tr_id": "H0STMKO0",
            "MKSC_SHRN_ISCD": "005930",
            "MKSC_STATUS": "OPEN",
            "MKSC_SESSION": "REGULAR",
        })
        result = parse_market_status(raw)
        assert isinstance(result, RealtimeMarketStatus)
        assert result.market_status == "OPEN"
        assert result.market_session == "REGULAR"
        assert result.parsed_ok is True


# ── parser: expected execution ─────────────────────────────────────────────────

class TestParseExpectedExecution:
    def test_parse_valid(self):
        raw = json.dumps({
            "tr_id": "H0STANC0",
            "MKSC_SHRN_ISCD": "005930",
            "STCK_ANT_CNTG_PRC": "71800",
            "ANT_CNTG_QTY": "5000",
            "ANT_CNTG_VS": "DOWN",
        })
        result = parse_expected_execution(raw)
        assert isinstance(result, RealtimeExpectedExecution)
        assert result.expected_price == 71800
        assert result.expected_volume == 5000
        assert result.expected_change == "DOWN"
        assert result.parsed_ok is True


# ── dispatch ─────────────────────────────────────────────────────────────────

class TestDispatch:
    def test_dispatch_trade_tick(self):
        raw = json.dumps({"tr_id": "H0STCNT0", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert isinstance(result, RealtimeTradeTick)
        assert result.parsed_ok is True

    def test_dispatch_order_book(self):
        raw = json.dumps({"tr_id": "H0STASP0", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert isinstance(result, RealtimeOrderBook)

    def test_dispatch_fill_notice(self):
        raw = json.dumps({"tr_id": "H0STCNI0", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert isinstance(result, RealtimeFillNotice)

    def test_dispatch_market_status(self):
        raw = json.dumps({"tr_id": "H0STMKO0", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert isinstance(result, RealtimeMarketStatus)

    def test_dispatch_expected_execution(self):
        raw = json.dumps({"tr_id": "H0STANC0", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert isinstance(result, RealtimeExpectedExecution)

    def test_dispatch_unknown(self):
        raw = json.dumps({"tr_id": "UNKNOWN_TR", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert result.parsed_ok is False
        assert "unknown tr_id: UNKNOWN_TR" in result.data_quality_warnings

    def test_dispatch_invalid_json(self):
        result = dispatch_message("not json at all")
        assert result.parsed_ok is False
        assert any("unparseable" in w.lower() for w in result.data_quality_warnings)

    def test_dispatch_missing_tr_id(self):
        result = dispatch_message('{"MKSC_SHRN_ISCD": "005930"}')
        assert result.parsed_ok is False


# ── raw message log prevention ───────────────────────────────────────────────

class TestNoRawLogging:
    """Parser must not include full raw message in output."""

    def test_trade_tick_does_not_contain_raw_body(self):
        raw_data = {
            "tr_id": "H0STCNT0",
            "MKSC_SHRN_ISCD": "005930",
            "STCK_PRPR": "72000",
        }
        raw = json.dumps(raw_data)
        result = parse_trade_tick(raw)
        # raw message should not be in any field
        for field_name, value in result.__dict__.items():
            if isinstance(value, str) and field_name != "raw_hash":
                assert "72000" not in value or field_name == "trade_price", \
                    f"raw data leaked in field {field_name}"

    def test_dispatch_result_has_no_raw_field(self):
        raw = json.dumps({"tr_id": "H0STCNT0", "MKSC_SHRN_ISCD": "005930"})
        result = dispatch_message(raw)
        assert not hasattr(result, "raw_text")
        assert not hasattr(result, "raw_body")
        assert not hasattr(result, "raw_data")


# ── WsMessageParser class ────────────────────────────────────────────────────

class TestWsMessageParserClass:
    def test_parser_uses_dispatch(self):
        parser = WsMessageParser()
        raw = json.dumps({"tr_id": "H0STCNT0", "MKSC_SHRN_ISCD": "005930"})
        result = parser.parse(raw)
        assert isinstance(result, RealtimeTradeTick)
        assert result.parsed_ok is True
