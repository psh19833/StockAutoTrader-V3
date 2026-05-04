"""Scheduler — Audit Event 보관 정책 관리

Application Log: 30일 보관
Audit Event Log: 최소 1년 보관
Raw API Log: 7~30일 보관
EOD Summary: 장기 보관
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """보관 정책

    Attributes:
        name: 정책명
        max_days: 최대 보관 일수
        description: 설명
    """
    name: str
    max_days: int
    description: str


# ── 기본 보관 정책 ──

DEFAULT_POLICIES: dict[str, RetentionPolicy] = {
    "application_log": RetentionPolicy(
        name="application_log",
        max_days=30,
        description="Application Log — 30일 보관, 날짜별 rotation",
    ),
    "audit_event_log": RetentionPolicy(
        name="audit_event_log",
        max_days=365,
        description="Audit Event Log — 최소 1년 보관, 검색 가능",
    ),
    "raw_api_log": RetentionPolicy(
        name="raw_api_log",
        max_days=30,
        description="Raw API Log — 7~30일 보관, 민감정보 마스킹",
    ),
    "eod_summary": RetentionPolicy(
        name="eod_summary",
        max_days=3650,  # 10년
        description="EOD Summary — 장기 보관",
    ),
}


def get_retention_policy(name: str) -> RetentionPolicy | None:
    """보관 정책 조회

    Args:
        name: 정책명

    Returns:
        RetentionPolicy 객체 또는 None
    """
    return DEFAULT_POLICIES.get(name)


def is_expired(policy: RetentionPolicy, days_old: int) -> bool:
    """보관 기간 만료 여부 확인

    Args:
        policy: 보관 정책
        days_old: 경과 일수

    Returns:
        만료 시 True
    """
    return days_old >= policy.max_days