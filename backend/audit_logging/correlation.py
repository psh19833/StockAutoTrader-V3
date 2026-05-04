"""Correlation ID 생성기 — 거래 흐름 연결"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional


def _now_tag() -> str:
    """현재 시각 기반 태그 생성 (YYMMDD-HHMMSS)"""
    return datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")


def _random_suffix(length: int = 6) -> str:
    """랜덤 접미사 생성"""
    return uuid.uuid4().hex[:length]


def correlation_id(prefix: str = "TRADE") -> str:
    """trade correlation_id 생성

    하나의 거래 흐름을 연결하는 기본 ID.
    SCAN → QUANT → STRATEGY → RISK → ORDER → FILL → POSITION

    Returns:
        "TRADE-YYMMDD-HHMMSS-xxxxxx"
    """
    return f"{prefix}-{_now_tag()}-{_random_suffix()}"


def scan_run_id() -> str:
    """스캔 실행 ID

    Returns:
        "SCAN-YYMMDD-HHMMSS-xxxxxx"
    """
    return correlation_id("SCAN")


def evaluation_id() -> str:
    """정량평가 실행 ID

    Returns:
        "EVAL-YYMMDD-HHMMSS-xxxxxx"
    """
    return correlation_id("EVAL")


def signal_id() -> str:
    """전략 신호 ID

    Returns:
        "SIG-YYMMDD-HHMMSS-xxxxxx"
    """
    return correlation_id("SIG")


def risk_decision_id() -> str:
    """리스크 결정 ID

    Returns:
        "RISK-YYMMDD-HHMMSS-xxxxxx"
    """
    return correlation_id("RISK")


def order_intent_id() -> str:
    """주문 의도 ID

    Returns:
        "ORD-YYMMDD-HHMMSS-xxxxxx"
    """
    return correlation_id("ORD")


def fill_id() -> str:
    """체결 ID

    Returns:
        "FILL-YYMMDD-HHMMSS-xxxxxx"
    """
    return correlation_id("FILL")