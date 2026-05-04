"""Logger — Log Sanitizer 적용 로거

Application Log 계층에 sanitizer를 적용한 logger wrapper.
Python 표준 logging 모듈과 이름 충돌 방지를 위해 sat3_logger로 명명.
"""
from __future__ import annotations

import logging
from typing import Any

from audit_logging.log_sanitizer import sanitize_dict


class SafeLogger:
    """Sanitizer 적용 Logger Wrapper

    모든 log message/extra data를 sanitize하여 민감정보 노출 방지.
    """

    def __init__(self, name: str, level: int = logging.INFO):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

    def _sanitize_msg(self, msg: str) -> str:
        """메시지 sanitize"""
        from audit_logging.log_sanitizer import sanitize_value
        result = sanitize_value("message", msg)
        return str(result) if not isinstance(result, str) else result

    def _sanitize_extra(self, extra: dict[str, Any] | None) -> dict[str, Any] | None:
        """extra dict sanitize"""
        if extra is None:
            return None
        return sanitize_dict(extra)

    def info(self, msg: str, *args, extra: dict[str, Any] | None = None, **kwargs) -> None:
        self._logger.info(self._sanitize_msg(msg), *args, extra=self._sanitize_extra(extra), **kwargs)

    def warning(self, msg: str, *args, extra: dict[str, Any] | None = None, **kwargs) -> None:
        self._logger.warning(self._sanitize_msg(msg), *args, extra=self._sanitize_extra(extra), **kwargs)

    def error(self, msg: str, *args, extra: dict[str, Any] | None = None, **kwargs) -> None:
        self._logger.error(self._sanitize_msg(msg), *args, extra=self._sanitize_extra(extra), **kwargs)

    def debug(self, msg: str, *args, extra: dict[str, Any] | None = None, **kwargs) -> None:
        self._logger.debug(self._sanitize_msg(msg), *args, extra=self._sanitize_extra(extra), **kwargs)

    def critical(self, msg: str, *args, extra: dict[str, Any] | None = None, **kwargs) -> None:
        self._logger.critical(self._sanitize_msg(msg), *args, extra=self._sanitize_extra(extra), **kwargs)