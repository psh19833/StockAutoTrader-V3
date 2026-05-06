"""KIS auth request helpers aligned with official open-trading-api examples."""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


KIS_PROD_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_VPS_BASE_URL = "https://openapivts.koreainvestment.com:29443"


@dataclass(frozen=True)
class DomainKeyDiagnostic:
    mode: str
    base_url: str
    expected_base_url: str
    is_match: bool
    warning_code: str
    warning_text: str


def build_kis_auth_headers(user_agent: str | None = None) -> dict[str, str]:
    """Official example-compatible auth headers.

    - Content-Type: application/json
    - Accept: text/plain
    - charset: UTF-8
    - User-Agent: KIS_USER_AGENT env or provided or SAT3/3.0
    """
    ua = user_agent or os.getenv("KIS_USER_AGENT", "").strip() or "SAT3/3.0"
    return {
        "Content-Type": "application/json",
        "Accept": "text/plain",
        "charset": "UTF-8",
        "User-Agent": ua,
    }


def infer_mode_from_base_url(base_url: str) -> str:
    host = (urlparse((base_url or "").strip()).netloc or "").lower()
    if "openapivts.koreainvestment.com" in host:
        return "vps"
    return "prod"


def validate_prod_vps_alignment(base_url: str, mode: str | None = None) -> DomainKeyDiagnostic:
    actual_mode = (mode or infer_mode_from_base_url(base_url)).lower()
    expected = KIS_PROD_BASE_URL if actual_mode == "prod" else KIS_VPS_BASE_URL
    normalized = (base_url or "").rstrip("/")
    is_match = normalized == expected
    return DomainKeyDiagnostic(
        mode=actual_mode,
        base_url=normalized,
        expected_base_url=expected,
        is_match=is_match,
        warning_code="" if is_match else "PROD_VPS_MISMATCH",
        warning_text="" if is_match else f"Base URL does not match mode={actual_mode}",
    )
