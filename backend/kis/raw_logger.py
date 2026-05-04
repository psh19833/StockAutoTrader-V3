"""KIS API Secret Masking 및 안전한 로깅

SAT3에서는 secret/token/account 정보가 로그에 절대 노출되지 않아야 한다.
이 모듈은 모든 로그 출력 전에 민감 정보를 마스킹한다.

마스킹 대상:
- app key: 앞 3자리 + **** + 뒤 4자리
- app secret: 앞 4자리 + **** + 뒤 4자리
- access token: 앞 3자리 + **** + 뒤 4자리
- 계좌번호: 앞 4자리 + **** + 뒤 2자리
- 텔레그램 bot token: 앞 4자리 + **** + 뒤 4자리
- 텔레그램 chat_id: 앞 4자리 + **** + 뒤 3자리
"""
from __future__ import annotations

import logging
import re
from typing import Any


def _mask_safe(value: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """문자열 중간을 ****로 마스킹"""
    if not value:
        return ""
    total = len(value)
    if total <= prefix_len + suffix_len:
        # 짧은 문자열은 앞뒤 절반만 유지
        mid = total // 2
        return value[:mid] + "*" * (total - mid)
    return value[:prefix_len] + "*" * 4 + value[-suffix_len:]


def mask_account_no(account_no: str) -> str:
    """계좌번호 마스킹: 앞 4자리 + **** + 뒤 2자리"""
    return _mask_safe(account_no, prefix_len=4, suffix_len=2)


def mask_app_key(app_key: str) -> str:
    """App Key 마스킹: 앞 3자리 + **** + 뒤 4자리"""
    return _mask_safe(app_key, prefix_len=3, suffix_len=4)


def mask_app_secret(secret: str) -> str:
    """App Secret 마스킹: 앞 4자리 + **** + 뒤 4자리"""
    return _mask_safe(secret, prefix_len=4, suffix_len=4)


def mask_token(token: str) -> str:
    """Access Token 마스킹: 앞 3자리 + **** + 뒤 4자리"""
    return _mask_safe(token, prefix_len=3, suffix_len=4)


def mask_telegram_bot_token(token: str) -> str:
    """텔레그램 Bot Token 마스킹: 앞 4자리 + **** + 뒤 4자리 (구분자 : 보존)"""
    if not token:
        return ""
    if ":" in token:
        prefix, suffix = token.split(":", 1)
        masked_prefix = _mask_safe(prefix, prefix_len=4, suffix_len=0)[:4]
        masked_suffix = _mask_safe(suffix, prefix_len=0, suffix_len=4)
        return masked_prefix + ":" + masked_suffix
    return _mask_safe(token, prefix_len=4, suffix_len=4)


def mask_telegram_chat_id(chat_id: str) -> str:
    """텔레그램 Chat ID 마스킹: 앞 4자리 + **** + 뒤 3자리"""
    return _mask_safe(chat_id, prefix_len=4, suffix_len=3)


# 민감 헤더 키 목록 (대소문자 무시)
_SENSITIVE_HEADER_KEYS: set[str] = {
    "authorization",
    "appkey",
    "appsecret",
    "tr_id",
}


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """HTTP 요청 헤더에서 민감 정보 마스킹

    Args:
        headers: 원본 헤더 딕셔너리

    Returns:
        민감 정보가 마스킹된 헤더 딕셔너리
    """
    result: dict[str, str] = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower == "authorization":
            # "Bearer <token>" 패턴
            if value.startswith("Bearer "):
                token = value[7:]
                result[key] = f"Bearer {mask_token(token)}"
            else:
                result[key] = mask_token(value)
        elif key_lower in ("appkey",):
            result[key] = mask_app_key(value)
        elif key_lower in ("appsecret",):
            result[key] = mask_app_secret(value)
        else:
            result[key] = value
    return result


# 정규식 기반 마스킹 패턴
_MASK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(account[=:_\s]?)(\d{8,12})'), lambda m: m.group(1) + mask_account_no(m.group(2))),
    (re.compile(r'(token[=:_\s]?)([A-Za-z0-9\-_.]{20,})'), lambda m: m.group(1) + mask_token(m.group(2))),
    (re.compile(r'(appkey[=:_\s]?)([A-Za-z0-9]{10,})', re.IGNORECASE), lambda m: m.group(1) + mask_app_key(m.group(2))),
    (re.compile(r'(secret[=:_\s]?)([A-Za-z0-9]{10,})', re.IGNORECASE), lambda m: m.group(1) + mask_app_secret(m.group(2))),
]


def _apply_patterns(text: str) -> str:
    """텍스트 내 모든 민감 패턴 마스킹"""
    for pattern, repl in _MASK_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class KisSafeLogger:
    """KIS API 전용 안전한 로거

    모든 로그 메시지는 출력 전에 secret/token/account 정보가 마스킹된다.
    """

    def __init__(self, name: str = "kis"):
        self._logger = logging.getLogger(name)

    def sanitize(self, message: str) -> str:
        """메시지 내 민감 정보 마스킹

        Args:
            message: 원본 로그 메시지

        Returns:
            마스킹 처리된 안전한 메시지
        """
        return _apply_patterns(message)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(self.sanitize(message), *args, **kwargs)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(self.sanitize(message), *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(self.sanitize(message), *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(self.sanitize(message), *args, **kwargs)