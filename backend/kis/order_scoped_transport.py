"""Order-scoped Transport

목적:
- RealTransport의 전역 주문 endpoint 차단을 유지하면서,
  submit-once live pilot 경로에서만 특정 주문 endpoint를 허용한다.

원칙:
- allowlist에 명시된 path prefix만 주문 endpoint 허용.
- 그 외 주문 endpoint는 그대로 차단.
- 이 클래스는 submit-once 스크립트에서만 명시적으로 생성해 사용한다.
"""

from __future__ import annotations

from typing import Iterable

from kis.transport import RealTransport


class OrderScopedRealTransport(RealTransport):
    def __init__(
        self,
        *,
        base_url: str,
        timeout: int = 30,
        allow_order_paths: Iterable[str] = (),
    ):
        super().__init__(base_url=base_url, timeout=timeout)
        self._allow_order_paths = tuple(str(p) for p in allow_order_paths)

    def _check_order_endpoint(self, path: str) -> None:  # type: ignore[override]
        # Allow only explicitly allowlisted order endpoints.
        from urllib.parse import urlparse

        parsed = urlparse(path)
        path_only = (parsed.path or path).split("?", 1)[0]

        if any(path_only.startswith(p) for p in self._allow_order_paths):
            return

        # Fallback to base policy (blocks all known order endpoints)
        return super()._check_order_endpoint(path)
