"""Serializers — DB 저장 전 secret sanitization

주의:
- 저장소에는 원문 secret/token을 남기지 않는다.
- Dashboard는 저장소의 값을 그대로 노출하지 않고, 항상 sanitized payload만 반환한다.

이 모듈은 "저장" 단계에서 1차적으로 민감 키를 제거한다.
"""

from __future__ import annotations

from typing import Any


_SECRET_KEYS: frozenset[str] = frozenset({
    # KIS / API secrets
    "appkey", "app_key", "appsecret", "app_secret",
    "api_key", "api_secret",
    "access_token", "refresh_token", "token",
    "authorization",
    "secret", "secret_key",
    "approval_key", "approval_secret",
    # Telegram secrets
    "telegram_bot_token", "bot_token", "telegram_token",
    # Potentially sensitive identifiers (allowed to display locally in some views,
    # but we still avoid persisting them in audit payloads by default)
    "account_no", "account_number",
    "chat_id",
})


def sanitize_for_storage(data: dict[str, Any]) -> dict[str, Any]:
    """민감 키를 제거한 dict 반환 (재귀)."""
    return {
        k: _sanitize_value(v)
        for k, v in data.items()
        if k.lower() not in _SECRET_KEYS
    }


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_for_storage(value)
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value
