"""KIS WebSocket endpoint catalog.

Defines all KIS WebSocket real-time data channels with their TR_IDs,
market codes, and channel types. This catalog is the single source of
truth for WebSocket subscription and message routing.

TR_ID reference (KIS Open API documentation):
  - H0STCNT0: 국내주식 실시간 체결가 (KRX)
  - H0STASP0: 국내주식 실시간 호가 (KRX)
  - H0STCNI0: 국내주식 실시간 체결통보
  - H0STMKO0: 국내주식 장운영정보 (통합)
  - H0STANC0: 국내주식 실시간 예상체결
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WsEndpoint:
    """Immutable descriptor for a single KIS WebSocket channel."""

    name: str            # e.g. "실시간 체결가"
    tr_id: str           # e.g. "H0STCNT0"
    channel_type: str    # "realtime" | "notification" | "control"
    market: str          # "KRX" | "NXT" | "통합"
    source: str = "KIS_API_WS"


# ── Endpoint Catalog ────────────────────────────────────────────────────────

KIS_WS_ENDPOINTS: list[WsEndpoint] = [
    WsEndpoint(
        name="실시간 체결가",
        tr_id="H0STCNT0",
        channel_type="realtime",
        market="KRX",
    ),
    WsEndpoint(
        name="실시간 호가",
        tr_id="H0STASP0",
        channel_type="realtime",
        market="KRX",
    ),
    WsEndpoint(
        name="실시간 체결통보",
        tr_id="H0STCNI0",
        channel_type="notification",
        market="통합",
    ),
    WsEndpoint(
        name="장운영정보",
        tr_id="H0STMKO0",
        channel_type="realtime",
        market="통합",
    ),
    WsEndpoint(
        name="실시간 예상체결",
        tr_id="H0STANC0",
        channel_type="realtime",
        market="KRX",
    ),
]


# ── TR_ID index (built once at import) ──────────────────────────────────────

_TR_ID_MAP: dict[str, WsEndpoint] = {e.tr_id: e for e in KIS_WS_ENDPOINTS}


def get_ws_endpoint(tr_id: Optional[str]) -> Optional[WsEndpoint]:
    """Look up a WebSocket endpoint by TR_ID.

    Returns None for unknown TR_IDs or empty/None input.
    """
    if not tr_id:
        return None
    return _TR_ID_MAP.get(tr_id)


def list_ws_endpoints() -> list[WsEndpoint]:
    """Return all registered WebSocket endpoints."""
    return list(KIS_WS_ENDPOINTS)
