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

    def get_json(self, path: str, params: dict | None = None,
                 headers: dict | None = None) -> TransportResponse:
        self.calls.append(("GET", path, params))
        if path in self._responses:
            return TransportResponse(200, self._responses[path])
        return TransportResponse(404, {"error": "not_found"})

    def post_json(self, path: str, json_data: dict | None = None,
                  headers: dict | None = None) -> TransportResponse:
        self.calls.append(("POST", path, json_data))
        if path in self._responses:
            return TransportResponse(200, self._responses[path])
        return TransportResponse(404, {"error": "not_found"})


class RealTransport:
    """운영용 Real Transport — 실제 KIS HTTP 호출

    requests/httpx 사용은 이 클래스 내부로만 격리한다.
    주문 endpoint는 get_json/post_json 진입 시 차단된다.
    """

    def __init__(self, base_url: str = "", timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _full_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self._base_url}{path}"

    def _check_order_endpoint(self, path: str) -> None:
        from kis.errors import OrderEndpointBlockedError
        order_paths = [
            "/uapi/domestic-stock/v1/trading/order-cash",
            "/uapi/domestic-stock/v1/trading/order-credit",
            "/uapi/domestic-stock/v1/trading/order-rvsecncl",
        ]
        if any(path.startswith(p) for p in order_paths):
            raise OrderEndpointBlockedError(f"Order endpoint blocked: {path}")

    def get_json(self, path: str, params: dict | None = None,
                 headers: dict | None = None) -> TransportResponse:
        self._check_order_endpoint(path)
        import urllib.request
        import json
        url = self._full_url(path)
        try:
            req = urllib.request.Request(url, method="GET")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return TransportResponse(
                    status_code=resp.status,
                    body=body if isinstance(body, dict) else {"data": body},
                )
        except urllib.error.HTTPError as e:
            return TransportResponse(status_code=e.code, body={"error": str(e)})
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error: {e}")
        except json.JSONDecodeError:
            return TransportResponse(status_code=200, body={"error": "json_parse_error"})
        except Exception as e:
            return TransportResponse(status_code=500, body={"error": str(e)})

    def post_json(self, path: str, json_data: dict | None = None,
                  headers: dict | None = None) -> TransportResponse:
        self._check_order_endpoint(path)
        import urllib.request
        import json
        url = self._full_url(path)
        try:
            data = json.dumps(json_data or {}).encode("utf-8")
            req_headers = {"Content-Type": "application/json"}
            if headers:
                req_headers.update(headers)
            req = urllib.request.Request(
                url, data=data, method="POST",
                headers=req_headers,
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return TransportResponse(
                    status_code=resp.status,
                    body=body if isinstance(body, dict) else {"data": body},
                )
        except urllib.error.HTTPError as e:
            return TransportResponse(status_code=e.code, body={"error": str(e)})
        except urllib.error.URLError as e:
            raise ConnectionError(f"Network error: {e}")
        except json.JSONDecodeError:
            return TransportResponse(status_code=200, body={"error": "json_parse_error"})
        except Exception as e:
            return TransportResponse(status_code=500, body={"error": str(e)})
