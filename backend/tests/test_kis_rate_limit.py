"""Phase 1 — TDD: KIS API Rate Limit 관리 테스트"""
import time
import pytest
from kis.rate_limit import (
    KisRateLimiter,
    RateLimitState,
    RateLimitExceeded,
    RateLimitConfig,
)


class TestRateLimitConfig:
    """RateLimitConfig 기본"""

    def test_default_values(self):
        """기본 설정값 확인"""
        cfg = RateLimitConfig()
        assert cfg.max_requests_per_second == 20
        assert cfg.max_requests_per_day == 30000

    def test_custom_values(self):
        """커스텀 설정 가능"""
        cfg = RateLimitConfig(max_requests_per_second=10, max_requests_per_day=1000)
        assert cfg.max_requests_per_second == 10
        assert cfg.max_requests_per_day == 1000


class TestKisRateLimiter:
    """KisRateLimiter 단위 테스트"""

    def test_initial_state(self):
        """초기 RateLimitState"""
        limiter = KisRateLimiter()
        state = limiter.get_state()
        assert state.remaining_second == 20
        assert state.remaining_day == 30000
        assert state.total_requests == 0

    def test_acquire_single_request(self):
        """단일 요청 acquire 후 상태 변화"""
        limiter = KisRateLimiter()
        limiter.acquire()
        state = limiter.get_state()
        assert state.remaining_second == 19
        assert state.total_requests == 1

    def test_acquire_multiple(self):
        """여러 요청 후 남은 초당 호출 감소"""
        limiter = KisRateLimiter()
        for _ in range(5):
            limiter.acquire()
        state = limiter.get_state()
        assert state.remaining_second == 15
        assert state.total_requests == 5

    def test_acquire_raises_when_exceeded(self):
        """초당 호출 초과 시 RateLimitExceeded 발생"""
        limiter = KisRateLimiter(max_per_second=3)
        for _ in range(3):
            limiter.acquire()
        with pytest.raises(RateLimitExceeded) as exc_info:
            limiter.acquire()
        assert "Second rate limit" in str(exc_info.value)

    def test_second_window_resets_after_time(self):
        """1초 후 초당 카운트 리셋"""
        limiter = KisRateLimiter(max_per_second=2, window_seconds=1)
        limiter.acquire()
        limiter.acquire()
        # 3번째는 차단
        with pytest.raises(RateLimitExceeded):
            limiter.acquire()
        # 1초 기다리면 리셋
        time.sleep(1.1)
        limiter.acquire()  # 성공
        state = limiter.get_state()
        assert state.remaining_second == 1

    def test_day_limit_exceeded(self):
        """일일 호출 초과 시 RateLimitExceeded 발생"""
        limiter = KisRateLimiter(max_per_second=100, max_per_day=2)
        limiter.acquire()
        limiter.acquire()
        with pytest.raises(RateLimitExceeded) as exc_info:
            limiter.acquire()
        assert "Daily rate limit" in str(exc_info.value)

    def test_state_total_requests(self):
        """전체 요청 수 추적"""
        limiter = KisRateLimiter()
        for _ in range(10):
            limiter.acquire()
        assert limiter.get_state().total_requests == 10

    def test_state_remaining_day(self):
        """남은 일일 호출 수"""
        limiter = KisRateLimiter(max_per_second=100, max_per_day=5)
        for _ in range(3):
            limiter.acquire()
        assert limiter.get_state().remaining_day == 2


class TestRateLimitState:
    """RateLimitState 데이터클래스"""

    def test_fields(self):
        """모든 필드 존재"""
        state = RateLimitState(
            remaining_second=15,
            remaining_day=25000,
            total_requests=100,
        )
        assert state.remaining_second == 15
        assert state.remaining_day == 25000
        assert state.total_requests == 100