"""Phase 1 — TDD: KIS API OAuth 인증 테스트"""
import pytest
from datetime import datetime, timedelta, timezone
from kis.auth import (
    KisAuthManager,
    KisToken,
    TokenState,
    AuthConfig,
    InvalidTokenError,
    TokenExpiredError,
)


class TestAuthConfig:
    """AuthConfig 기본"""

    def test_default_fields(self):
        cfg = AuthConfig()
        assert cfg.token_refresh_margin == 3600

    def test_custom_margin(self):
        cfg = AuthConfig(token_refresh_margin=600)
        assert cfg.token_refresh_margin == 600


class TestKisToken:
    """KisToken 데이터클래스"""

    @pytest.fixture
    def sample_token(self):
        return KisToken(
            access_token="eyJhbGciOiJIUzI1NiJ9.test_token_value",
            token_type="Bearer",
            expires_in=86400,
            issued_at=datetime.now(timezone.utc),
        )

    def test_token_fields(self, sample_token):
        assert sample_token.access_token.startswith("eyJ")
        assert sample_token.token_type == "Bearer"
        assert sample_token.expires_in == 86400

    def test_is_expired_true_when_elapsed(self, sample_token):
        """만료 시간이 지나면 True"""
        old = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=0,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert old.is_expired is True

    def test_is_expired_false_when_valid(self, sample_token):
        """만료되지 않았으면 False"""
        assert sample_token.is_expired is False

    def test_expires_at_calculated(self, sample_token):
        """expires_at이 정확히 계산"""
        expected = sample_token.issued_at + timedelta(seconds=sample_token.expires_in)
        assert abs((sample_token.expires_at - expected).total_seconds()) < 1


class TestTokenState:
    """TokenState Enum"""

    def test_states_exist(self):
        assert TokenState.VALID
        assert TokenState.EXPIRED
        assert TokenState.REFRESHING
        assert TokenState.NONE


class TestKisAuthManager:
    """KisAuthManager — 토큰 생명주기 관리"""

    def test_initial_state(self):
        """초기에는 토큰 없음"""
        mgr = KisAuthManager()
        assert mgr.get_state() == TokenState.NONE
        assert mgr.get_token() is None

    def test_set_token(self):
        """토큰 설정"""
        mgr = KisAuthManager()
        token = KisToken(
            access_token="test_token",
            token_type="Bearer",
            expires_in=86400,
            issued_at=datetime.now(timezone.utc),
        )
        mgr.set_token(token)
        assert mgr.get_token() == token
        assert mgr.get_state() == TokenState.VALID

    def test_clear_token(self):
        """토큰 제거"""
        mgr = KisAuthManager()
        token = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=86400,
            issued_at=datetime.now(timezone.utc),
        )
        mgr.set_token(token)
        mgr.clear_token()
        assert mgr.get_token() is None
        assert mgr.get_state() == TokenState.NONE

    def test_is_token_expired_returns_true(self):
        """만료된 토큰 감지"""
        mgr = KisAuthManager()
        old = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=0,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        mgr.set_token(old)
        assert mgr.get_state() == TokenState.EXPIRED

    def test_needs_refresh_when_no_token(self):
        """토큰 없으면 refresh 필요"""
        mgr = KisAuthManager()
        assert mgr.needs_refresh() is True

    def test_needs_refresh_when_expired(self):
        """만료된 토큰은 refresh 필요"""
        mgr = KisAuthManager()
        old = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=0,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        mgr.set_token(old)
        assert mgr.needs_refresh() is True

    def test_needs_refresh_when_valid(self):
        """유효한 토큰은 refresh 불필요"""
        mgr = KisAuthManager()
        valid = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=86400,
            issued_at=datetime.now(timezone.utc),
        )
        mgr.set_token(valid)
        assert mgr.needs_refresh() is False

    def test_needs_refresh_with_margin(self):
        """만료 임박(여유 시간 내)이면 refresh 필요"""
        mgr = KisAuthManager(margin_seconds=3600)
        # 30분 후 만료 → margin(3600초) 내
        almost_expired = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=1800,
            issued_at=datetime.now(timezone.utc),
        )
        mgr.set_token(almost_expired)
        assert mgr.needs_refresh() is True

    def test_require_valid_token_raises_when_none(self):
        """토큰 없을 때 require_valid_token() 예외"""
        mgr = KisAuthManager()
        with pytest.raises(InvalidTokenError):
            mgr.require_valid_token()

    def test_require_valid_token_raises_when_expired(self):
        """토큰 만료 시 require_valid_token() 예외"""
        mgr = KisAuthManager()
        old = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=0,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        mgr.set_token(old)
        with pytest.raises(TokenExpiredError):
            mgr.require_valid_token()

    def test_require_valid_token_returns_token_when_valid(self):
        """유효한 토큰은 정상 반환"""
        mgr = KisAuthManager()
        valid = KisToken(
            access_token="test",
            token_type="Bearer",
            expires_in=86400,
            issued_at=datetime.now(timezone.utc),
        )
        mgr.set_token(valid)
        result = mgr.require_valid_token()
        assert result == valid

    def test_get_authorization_header(self):
        """Authorization 헤더 생성"""
        mgr = KisAuthManager()
        valid = KisToken(
            access_token="my_test_token_value",
            token_type="Bearer",
            expires_in=86400,
            issued_at=datetime.now(timezone.utc),
        )
        mgr.set_token(valid)
        header = mgr.get_authorization_header()
        assert header == {"authorization": "Bearer my_test_token_value"} | {"appkey": mgr._app_key, "appsecret": mgr._app_secret}

    def test_get_authorization_header_raises_when_no_token(self):
        """토큰 없으면 헤더 생성 시 예외"""
        mgr = KisAuthManager()
        with pytest.raises(InvalidTokenError):
            mgr.get_authorization_header()

    def test_refresh_callback(self):
        """refresh 콜백 설정 및 호출"""
        mgr = KisAuthManager()
        callback_called = False

        def refresh_cb() -> KisToken:
            nonlocal callback_called
            callback_called = True
            return KisToken(
                access_token="new_token",
                token_type="Bearer",
                expires_in=86400,
                issued_at=datetime.now(timezone.utc),
            )

        mgr.set_refresh_callback(refresh_cb)
        mgr.refresh_token()
        assert callback_called is True
        assert mgr.get_token() is not None
        assert mgr.get_token().access_token == "new_token"

    def test_refresh_without_callback_raises(self):
        """콜백 없이 refresh 호출 시 예외"""
        mgr = KisAuthManager()
        with pytest.raises(RuntimeError):
            mgr.refresh_token()