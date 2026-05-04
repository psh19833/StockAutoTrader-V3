"""KIS API Rate Limit 관리

KIS API의 초당/일일 호출 제한을 준수하기 위한 Rate Limiter.
실전 호출 전에 반드시 이 limiter를 통과해야 한다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from collections import deque


class RateLimitExceeded(Exception):
    """Rate Limit 초과 시 발생"""
    def __init__(self, message: str):
        self.message_text = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"RateLimitExceeded: {self.message_text}"


@dataclass
class RateLimitConfig:
    """Rate Limit 설정

    KIS API 제한:
    - 초당 최대 20회 (기본)
    - 일일 최대 30,000회 (기본)
    """
    max_requests_per_second: int = 20
    max_requests_per_day: int = 30000


@dataclass
class RateLimitState:
    """현재 Rate Limit 상태"""
    remaining_second: int
    remaining_day: int
    total_requests: int


class KisRateLimiter:
    """KIS API Rate Limiter

    슬라이딩 윈도우로 초당 호출을 추적하고,
    누적 카운터로 일일 호출을 관리한다.
    """

    def __init__(
        self,
        max_per_second: int = 20,
        max_per_day: int = 30000,
        window_seconds: float = 1.0,
    ):
        self._max_per_second = max_per_second
        self._max_per_day = max_per_day
        self._window_seconds = window_seconds
        self._second_window: deque[float] = deque()
        self._day_count = 0

    def acquire(self) -> None:
        """Rate Limit을 확인하고 소모한다.

        Raises:
            RateLimitExceeded: 초당 또는 일일 한도를 초과한 경우
        """
        now = time.monotonic()

        # 초당 윈도우 정리 (오래된 타임스탬프 제거)
        while self._second_window and (now - self._second_window[0]) > self._window_seconds:
            self._second_window.popleft()

        # 일일 한도 확인
        if self._day_count >= self._max_per_day:
            raise RateLimitExceeded(
                f"Daily rate limit exceeded ({self._max_per_day}/{self._max_per_day})"
            )

        # 초당 한도 확인
        if len(self._second_window) >= self._max_per_second:
            raise RateLimitExceeded(
                f"Second rate limit exceeded ({self._max_per_second}/sec)"
            )

        # 요청 기록
        self._second_window.append(now)
        self._day_count += 1

    def get_state(self) -> RateLimitState:
        """현재 Rate Limit 상태 반환"""
        now = time.monotonic()
        while self._second_window and (now - self._second_window[0]) > self._window_seconds:
            self._second_window.popleft()

        return RateLimitState(
            remaining_second=self._max_per_second - len(self._second_window),
            remaining_day=self._max_per_day - self._day_count,
            total_requests=self._day_count,
        )