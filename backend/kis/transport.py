"""KisTransport — KIS API 통신 계층

StubTransport: 테스트 전용 (실제 네트워크 호출 없음)
RealTransport: 운영용 skeleton (N5 이후 구현)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


class KisTransport(Protocol):
    def get_json(self, path: str, params: dict | None = None) -> TransportResponse: ...
    def post_json(self, path: str, json_data: dict | None = None) -> TransportResponse: ...


class StubTransport:
    """테스트 전용 Stub — 실제 HTTP 호출 없음"""

    def __init__(self, responses: dict[str, dict] | None = None):
        self._responses = responses or {}
        self.calls: list[tuple[str, str, dict | None]] = []

    def get_json(self, path: str, params: dict | None = None) -> TransportResponse:
        self.calls.append(("GET", path, params))
        if path in self._responses:
            return TransportResponse(200, self._responses[path])
        return TransportResponse(404, {"error": "not_found"})

    def post_json(self, path: str, json_data: dict | None = None) -> TransportResponse:
        self.calls.append(("POST", path, json_data))
        if path in self._responses:
            return TransportResponse(200, self._responses[path])
        return TransportResponse(404, {"error": "not_found"})
