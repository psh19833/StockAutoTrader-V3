"""KIS WebSocket raw message parser.

WebSocket을 통해 수신한 raw JSON 문자열을 type-safe 모델로 파싱한다.

핵심 원칙:
  - raw message 전체는 저장/로그하지 않는다 (raw_hash만 기록)
  - 알 수 없는 TR_ID는 parsed_ok=False로 처리
  - JSON 파싱 실패도 parsed_ok=False + data_quality_warnings
  - 실패 시 추정값/임의값을 절대 채우지 않는다
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from kis.ws_models import (
    WebSocketMessageBase,
    RealtimeTradeTick,
    RealtimeOrderBook,
    RealtimeFillNotice,
    RealtimeMarketStatus,
    RealtimeExpectedExecution,
)


def compute_raw_hash(raw_message: str) -> str:
    """Compute SHA-256 hash of raw message for audit trail.

    원문 대신 해시만 기록하여 데이터 무결성 검증에 사용.
    """
    return hashlib.sha256(raw_message.encode("utf-8")).hexdigest()


def _safe_int(value) -> Optional[int]:
    """Safely convert a string to int, return None on failure."""
    if value is None:
        return None
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return None


# ── Per-TR_ID parsers ────────────────────────────────────────────────────────

def parse_trade_tick(raw: str) -> RealtimeTradeTick:
    """Parse H0STCNT0 실시간 체결가 message."""
    h = compute_raw_hash(raw)
    warnings: list[str] = []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return RealtimeTradeTick(
            parsed_ok=False,
            data_quality_warnings=["invalid json"],
            raw_hash=h,
        )

    symbol = str(data.get("MKSC_SHRN_ISCD", ""))
    if not symbol:
        warnings.append("symbol_missing")

    return RealtimeTradeTick(
        symbol=symbol,
        trade_price=_safe_int(data.get("STCK_PRPR")),
        trade_volume=_safe_int(data.get("CNTG_VOL")),
        trade_time=str(data.get("STCK_CNTG_HOUR", "")) or None,
        raw_hash=h,
        data_quality_warnings=warnings,
        parsed_ok=True,
    )


def parse_order_book(raw: str) -> RealtimeOrderBook:
    """Parse H0STASP0 실시간 호가 message."""
    h = compute_raw_hash(raw)
    warnings: list[str] = []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return RealtimeOrderBook(
            parsed_ok=False,
            data_quality_warnings=["invalid json"],
            raw_hash=h,
        )

    symbol = str(data.get("MKSC_SHRN_ISCD", ""))
    if not symbol:
        warnings.append("symbol_missing")

    # Ask/Bid prices and volumes (10 levels each in KIS)
    ask_prices = []
    bid_prices = []
    ask_volumes = []
    bid_volumes = []
    for i in range(1, 11):
        ap = _safe_int(data.get(f"ASKP{i}"))
        bp = _safe_int(data.get(f"BIDP{i}"))
        av = _safe_int(data.get(f"ASKP_RSQN{i}"))
        bv = _safe_int(data.get(f"BIDP_RSQN{i}"))
        if ap is not None:
            ask_prices.append(ap)
        if bp is not None:
            bid_prices.append(bp)
        if av is not None:
            ask_volumes.append(av)
        if bv is not None:
            bid_volumes.append(bv)

    return RealtimeOrderBook(
        symbol=symbol,
        ask_prices=ask_prices,
        bid_prices=bid_prices,
        ask_volumes=ask_volumes,
        bid_volumes=bid_volumes,
        total_ask_volume=_safe_int(data.get("TOTAL_ASKP_RSQN")),
        total_bid_volume=_safe_int(data.get("TOTAL_BIDP_RSQN")),
        raw_hash=h,
        data_quality_warnings=warnings,
        parsed_ok=True,
    )


def parse_fill_notice(raw: str) -> RealtimeFillNotice:
    """Parse H0STCNI0 실시간 체결통보 message."""
    h = compute_raw_hash(raw)
    warnings: list[str] = []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return RealtimeFillNotice(
            parsed_ok=False,
            data_quality_warnings=["invalid json"],
            raw_hash=h,
        )

    symbol = str(data.get("MKSC_SHRN_ISCD", ""))
    if not symbol:
        warnings.append("symbol_missing")

    return RealtimeFillNotice(
        symbol=symbol,
        order_number=str(data.get("ODNO", "")) or None,
        fill_price=_safe_int(data.get("FTNG_ORD_PRC")),
        fill_volume=_safe_int(data.get("FTNG_ORD_QTY")),
        raw_hash=h,
        data_quality_warnings=warnings,
        parsed_ok=True,
    )


def parse_market_status(raw: str) -> RealtimeMarketStatus:
    """Parse H0STMKO0 장운영정보 message."""
    h = compute_raw_hash(raw)
    warnings: list[str] = []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return RealtimeMarketStatus(
            parsed_ok=False,
            data_quality_warnings=["invalid json"],
            raw_hash=h,
        )

    symbol = str(data.get("MKSC_SHRN_ISCD", ""))
    if not symbol:
        warnings.append("symbol_missing")

    return RealtimeMarketStatus(
        symbol=symbol,
        market_status=str(data.get("MKSC_STATUS", "")) or None,
        market_session=str(data.get("MKSC_SESSION", "")) or None,
        raw_hash=h,
        data_quality_warnings=warnings,
        parsed_ok=True,
    )


def parse_expected_execution(raw: str) -> RealtimeExpectedExecution:
    """Parse H0STANC0 실시간 예상체결 message."""
    h = compute_raw_hash(raw)
    warnings: list[str] = []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return RealtimeExpectedExecution(
            parsed_ok=False,
            data_quality_warnings=["invalid json"],
            raw_hash=h,
        )

    symbol = str(data.get("MKSC_SHRN_ISCD", ""))
    if not symbol:
        warnings.append("symbol_missing")

    return RealtimeExpectedExecution(
        symbol=symbol,
        expected_price=_safe_int(data.get("STCK_ANT_CNTG_PRC")),
        expected_volume=_safe_int(data.get("ANT_CNTG_QTY")),
        expected_change=str(data.get("ANT_CNTG_VS", "")) or None,
        raw_hash=h,
        data_quality_warnings=warnings,
        parsed_ok=True,
    )


# ── TR_ID dispatch table ─────────────────────────────────────────────────────

# KIS WebSocket pipe-delimited field mapping per TR_ID
# Format: "0|TR_ID|symbol|field1|field2|..."
_PIPE_TR_FIELDS = {
    "H0STCNT0": ["tr_type", "tr_id", "MKSC_SHRN_ISCD", "STCK_PRPR", "CNTG_VOL",
                  "STCK_CNTG_HOUR", "change_sign", "change_price"],
    "H0STASP0": ["tr_type", "tr_id", "MKSC_SHRN_ISCD",
                  "ASKP1", "ASKP2", "ASKP3", "ASKP4", "ASKP5",
                  "ASKP6", "ASKP7", "ASKP8", "ASKP9", "ASKP10",
                  "BIDP1", "BIDP2", "BIDP3", "BIDP4", "BIDP5",
                  "BIDP6", "BIDP7", "BIDP8", "BIDP9", "BIDP10"],
    "H0STCNI0": ["tr_type", "tr_id", "MKSC_SHRN_ISCD", "ODNO",
                  "FTNG_ORD_PRC", "FTNG_ORD_QTY"],
    "H0STMKO0": ["tr_type", "tr_id", "MKSC_SHRN_ISCD",
                  "MKSC_STATUS", "MKSC_SESSION"],
    "H0STANC0": ["tr_type", "tr_id", "MKSC_SHRN_ISCD",
                  "STCK_ANT_CNTG_PRC", "ANT_CNTG_QTY", "ANT_CNTG_VS"],
}


def _parse_pipe_delimited(raw: str) -> dict | None:
    """Parse KIS WebSocket pipe-delimited format into a dict.

    Format: "0|TR_ID|symbol|field1|field2|..."

    Returns None if unparseable.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    parts = raw.strip().split("|")
    if len(parts) < 2:
        return None
    tr_id = parts[1] if len(parts) > 1 else ""
    fields = _PIPE_TR_FIELDS.get(tr_id)
    if fields is None:
        # Unknown TR_ID: try generic mapping
        return {"tr_id": tr_id}
    result = {}
    for i, field_name in enumerate(fields):
        if i < len(parts):
            result[field_name] = parts[i]
        else:
            break
    return result


_DISPATCH_TABLE = {
    "H0STCNT0": parse_trade_tick,
    "H0STASP0": parse_order_book,
    "H0STCNI0": parse_fill_notice,
    "H0STMKO0": parse_market_status,
    "H0STANC0": parse_expected_execution,
}


def dispatch_message(raw: str) -> WebSocketMessageBase:
    """Parse raw WebSocket message and dispatch to the correct model.

    TR_ID 기준으로 적절한 parser를 선택하고, 알 수 없는 TR_ID는
    parsed_ok=False인 WebSocketMessageBase를 반환한다.

    지원 형식:
      - JSON: {"tr_id": "H0STCNT0", ...}
      - Pipe-delimited: "0|H0STCNT0|005930|..." (KIS WebSocket 기본)

    이 함수는 raw 전문 전체를 로그/저장하지 않으며, raw_hash만 보존한다.
    """
    h = compute_raw_hash(raw)

    # Try JSON first
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Try pipe-delimited format
        data = _parse_pipe_delimited(raw)

    if data is None:
        return WebSocketMessageBase(
            parsed_ok=False,
            data_quality_warnings=["unparseable message format"],
            raw_hash=h,
        )

    if not isinstance(data, dict):
        return WebSocketMessageBase(
            parsed_ok=False,
            data_quality_warnings=["unparseable message format"],
            raw_hash=h,
        )

    tr_id = str(data.get("tr_id", "") or data.get("TR_ID", "") or "")

    if not tr_id:
        return WebSocketMessageBase(
            parsed_ok=False,
            data_quality_warnings=["missing tr_id"],
            raw_hash=h,
        )

    parser = _DISPATCH_TABLE.get(tr_id)
    if parser is None:
        return WebSocketMessageBase(
            tr_id=tr_id,
            symbol=str(data.get("MKSC_SHRN_ISCD", "")),
            parsed_ok=False,
            data_quality_warnings=[f"unknown tr_id: {tr_id}"],
            raw_hash=h,
        )

    return parser(raw)


class WsMessageParser:
    """WebSocket message parser with dispatch-based routing.

    Usage:
        parser = WsMessageParser()
        result = parser.parse(raw_json_string)
        # result is a typed model (RealtimeTradeTick, RealtimeOrderBook, etc.)
    """

    def parse(self, raw: str) -> WebSocketMessageBase:
        """Parse a raw WebSocket message to its typed model."""
        return dispatch_message(raw)
