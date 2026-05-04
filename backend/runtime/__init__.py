"""REST/WS Data Router Policy.

Defines when to use REST vs WebSocket for market data and fallback rules.

Policy:
  - 초기값: REST snapshot
  - 실시간 갱신: WebSocket stream
  - WS 장애 시: REST fallback
  - 추정값 생성 금지
  - source=KIS_API_REST / KIS_API_WS
"""

from __future__ import annotations

from enum import Enum


class DataSource(Enum):
    REST = "KIS_API_REST"
    WS = "KIS_API_WS"


class RouterMode(Enum):
    REST_ONLY = "REST_ONLY"
    WS_PRIMARY = "WS_PRIMARY"
    REST_FALLBACK = "REST_FALLBACK"


# ── Policy rules ─────────────────────────────────────────────────────────────

def initial_source() -> DataSource:
    """초기 데이터는 항상 REST에서 로드."""
    return DataSource.REST


def live_source(ws_connected: bool) -> DataSource:
    """WS 연결 상태에 따라 현재 데이터 소스 결정."""
    return DataSource.WS if ws_connected else DataSource.REST


def router_mode(ws_connected: bool, ws_was_connected: bool) -> RouterMode:
    """Determine router operation mode."""
    if ws_connected:
        return RouterMode.WS_PRIMARY
    if ws_was_connected:
        return RouterMode.REST_FALLBACK
    return RouterMode.REST_ONLY
