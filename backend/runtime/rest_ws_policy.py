"""REST/WS Data Router Policy."""
from enum import Enum


class DataSource(Enum):
    REST = "KIS_API_REST"
    WS = "KIS_API_WS"


class RouterMode(Enum):
    REST_ONLY = "REST_ONLY"
    WS_PRIMARY = "WS_PRIMARY"
    REST_FALLBACK = "REST_FALLBACK"


def initial_source() -> DataSource:
    return DataSource.REST


def live_source(ws_connected: bool) -> DataSource:
    return DataSource.WS if ws_connected else DataSource.REST


def router_mode(ws_connected: bool, ws_was_connected: bool) -> RouterMode:
    if ws_connected:
        return RouterMode.WS_PRIMARY
    if ws_was_connected:
        return RouterMode.REST_FALLBACK
    return RouterMode.REST_ONLY
