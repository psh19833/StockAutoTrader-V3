"""Log Sanitizer — 민감정보 마스킹

어떤 로그에도 Secret/Token/Account/Chat_ID 원문이 노출되지 않도록 보장한다.
dict, list, string 모두 재귀적으로 sanitizing 가능해야 한다.
"""
from __future__ import annotations

import re
from typing import Any


# ── 민감 패턴 정의 ──

# 민감 필드명 (대소문자 무관)
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "appkey", "app_key", "appsecret", "app_secret",
    "access_token", "access.token", "accesstoken",
    "refresh_token", "refresh.token", "refreshtoken",
    "approval_key", "approvalkey",
    "telegram_bot_token", "telegrambottoken",
    "authorization",
    "secret", "api_secret", "api_key",
})

# Also treat common ENV var names as sensitive when they appear as keys.
SENSITIVE_ENV_NAMES: frozenset[str] = frozenset({
    "telegram_bot_token",
    "telegrambottoken",
    "telegram_bot_token".upper().lower(),
    "kis_app_secret",
    "kis_app_secret".upper().lower(),
})

# 계좌번호 패턴: 8자리 숫자-2자리 (예: 12345678-01)
_ACCOUNT_PATTERN = re.compile(r"\b(\d{8})-(\d{2})\b")

# 토큰 패턴 (JWT 또는 유사 구조)
# - JWT: xxxxx.yyyyy.zzzzz
# - Long opaque tokens: 24+ safe chars
_TOKEN_PATTERN = re.compile(
    r"\b(?:[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{24,})\b"
)

# Telegram Bot Token 패턴
_TELEGRAM_BOT_PATTERN = re.compile(r"\b(\d{5,15}:[A-Za-z0-9_-]{20,})\b")

# Chat ID 패턴 (일반 숫자, -100 접두사 패턴 포함)
# 8자리 이상의 숫자만 Chat ID로 간주 (005930 같은 종목코드와 구분)
_CHAT_ID_PATTERN = re.compile(r"\b(-?\d{8,})\b")


def _mask_token(token: str) -> str:
    """토큰/Secret 마스킹

    Returns:
        처음 4자 + **** + 마지막 4자 (16자 미만이면 전체 마스킹)
    """
    if len(token) <= 8:
        return token[:2] + "****"
    return token[:4] + "****" + token[-4:]


def _mask_account(account: str) -> str:
    """계좌번호 마스킹: 12345678-01 → 1234****-**"""
    parts = account.split("-")
    if len(parts) == 2 and len(parts[0]) >= 4:
        return parts[0][:4] + "****-" + parts[1][:2]
    return _mask_token(account)


def _mask_telegram_token(token: str) -> str:
    """Telegram Bot Token 마스킹"""
    parts = token.split(":", 1)
    if len(parts) == 2 and len(parts[0]) >= 3:
        return parts[0][:3] + "****:" + _mask_token(parts[1])
    return _mask_token(token)


def _mask_chat_id(chat_id: str) -> str:
    """Chat ID 마스킹: 앞 3자 유지 + ****"""
    if len(chat_id) <= 4:
        return "****"
    return chat_id[:3] + "****"


def sanitize_value(key: str, value: Any, depth: int = 0) -> Any:
    """값을 sanitize (재귀)

    Args:
        key: 필드명 (대소문자 무관)
        value: sanitize할 값
        depth: 재귀 깊이 (무한 루프 방지)

    Returns:
        sanitize된 값
    """
    if depth > 20:
        return value

    key_lower = key.lower().replace(" ", "").replace(".", "_")

    # If the key itself is a known sensitive/ENV name, redact the value early.
    # (prevents secret-like values from leaking even if nested under unusual structures)
    if key_lower in _normalize_field_names(key_lower) or key_lower in SENSITIVE_ENV_NAMES:
        if isinstance(value, str):
            return _mask_token(value)
        return "[REDACTED]"

    # dict: 재귀 처리 (민감 키는 제거)
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            k_norm = str(k).lower().replace(" ", "").replace(".", "_")
            if k_norm in _normalize_field_names(k_norm) or k_norm in SENSITIVE_ENV_NAMES:
                # Drop sensitive keys entirely so API/audit payloads don't even mention them.
                continue
            cleaned[k] = sanitize_value(str(k), v, depth + 1)
        return cleaned

    # list: 각 항목 재귀 처리
    if isinstance(value, list):
        return [sanitize_value(key, v, depth + 1) for v in value]

    # 문자열 처리
    if isinstance(value, str):
        return _sanitize_string(key_lower, value)

    return value


def _sanitize_string(key_lower: str, value: str) -> str:
    """문자열 값 sanitize

    민감 필드명이면 해당 패턴으로 마스킹.
    일반 문자열이면 regex 기반 패턴 스캔.
    """
    # 민감 필드명 확인
    if key_lower in _normalize_field_names(key_lower):
        # 민감 필드 — 전체 값 마스킹
        return _mask_token(value)

    # 계좌번호 패턴
    if _ACCOUNT_PATTERN.search(value):
        return _ACCOUNT_PATTERN.sub(lambda m: _mask_account(m.group(0)), value)

    # Telegram Bot Token
    if _TELEGRAM_BOT_PATTERN.search(value):
        return _TELEGRAM_BOT_PATTERN.sub(lambda m: _mask_telegram_token(m.group(0)), value)

    # Chat ID (8자리 이상 숫자)
    # 주의: 일반 숫자 데이터와 구분 필요
    if _CHAT_ID_PATTERN.search(value) and len(value.strip("-")) >= 8:
        return _CHAT_ID_PATTERN.sub(lambda m: _mask_chat_id(m.group(0)), value)

    # JWT/Token 패턴 (20자 이상 base64url)
    if len(value) >= 20:
        if _TOKEN_PATTERN.search(value):
            return _TOKEN_PATTERN.sub(lambda m: _mask_token(m.group(0)), value)

    return value


def _normalize_field_names(key_lower: str) -> set[str]:
    """민감 필드명 정규화"""
    result: set[str] = set()
    for name in SENSITIVE_FIELD_NAMES:
        normalized = name.replace(".", "_").replace(" ", "")
        result.add(normalized)
    return result


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """AuditEvent payload sanitize

    Payload 내의 모든 민감정보를 재귀적으로 마스킹.
    """
    return sanitize_value("payload", payload)  # type: ignore


def sanitize_dict(d: dict[str, Any]) -> dict[str, Any]:
    """dict 전체 sanitize"""
    return sanitize_value("root", d)  # type: ignore