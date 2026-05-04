"""Serializers — DB 저장 전 secret sanitization"""
import json
from typing import Any

_SECRET_KEYS = frozenset({
    "app_key", "app_secret", "api_key", "api_secret",
    "access_token", "token", "secret", "secret_key",
    "account_no", "account_number",
    "chat_id", "bot_token", "telegram_token",
    "approval_key", "approval_secret",
})


def sanitize_for_storage(data: dict[str, Any]) -> dict[str, Any]:
    """민감 키를 제거한 dict 반환"""
    return {k: _sanitize_value(v) for k, v in data.items()
            if k.lower() not in _SECRET_KEYS}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_for_storage(value)
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value
