"""Phase 1 — TDD: KIS 에러 코드 매핑 테스트"""
import pytest
from kis.errors import (
    KisApiError,
    KisAuthError,
    KisRateLimitError,
    KisServerError,
    KIS_ERROR_CODES,
    classify_kis_error,
    KisErrorCategory,
)


class TestKisErrorCodes:
    """KIS API 에러 코드 상수"""

    def test_error_code_dict_defined(self):
        """KIS_ERROR_CODES가 dict이며 비어있지 않음"""
        assert isinstance(KIS_ERROR_CODES, dict)
        assert len(KIS_ERROR_CODES) > 0

    def test_error_code_has_category(self):
        """각 에러 코드에 category Enum이 있음"""
        for code, info in KIS_ERROR_CODES.items():
            assert isinstance(info.category, KisErrorCategory), (
                f"Code {code} category is not KisErrorCategory"
            )

    def test_error_code_has_message(self):
        """각 에러 코드에 message 문자열이 있음"""
        for code, info in KIS_ERROR_CODES.items():
            assert isinstance(info.message, str), f"Code {code} message is not str"
            assert len(info.message) > 0, f"Code {code} message is empty"


class TestClassifyKisError:
    """classify_kis_error 함수"""

    def test_known_auth_error(self):
        """알려진 인증 에러 코드 분류"""
        result = classify_kis_error("EGW00123")
        assert result is not None
        assert result.category == KisErrorCategory.AUTH

    def test_known_rate_limit_error(self):
        """알려진 Rate Limit 에러 코드 분류"""
        result = classify_kis_error("EGW00212")
        assert result is not None
        assert result.category == KisErrorCategory.RATE_LIMIT

    def test_known_system_error(self):
        """알려진 시스템 에러 코드 분류"""
        result = classify_kis_error("EGW00150")
        assert result is not None
        assert result.category == KisErrorCategory.SERVER

    def test_known_invalid_param_error(self):
        """알려진 파라미터 오류 코드 분류"""
        result = classify_kis_error("EGW00101")
        assert result is not None
        assert result.category == KisErrorCategory.INVALID_PARAM

    def test_unknown_error_code(self):
        """모르는 에러 코드는 None 반환"""
        result = classify_kis_error("UNKNOWN_CODE_99999")
        assert result is None

    def test_api_error_has_message(self):
        """classify 결과에 message 포함"""
        result = classify_kis_error("EGW00123")
        assert result is not None
        assert isinstance(result.message, str)
        assert len(result.message) > 0


class TestKisApiError:
    """KisApiError 예외 클래스"""

    def test_basic_exception(self):
        """KisApiError 기본 생성"""
        err = KisApiError(
            error_code="EGW00123",
            message="인증 실패",
            endpoint="/oauth2/tokenP",
        )
        assert err.error_code == "EGW00123"
        assert err.message_text == "인증 실패"
        assert err.endpoint == "/oauth2/tokenP"

    def test_exception_is_derived(self):
        """Exception을 상속"""
        err = KisApiError("EGW00123", "test", "/test")
        assert isinstance(err, Exception)

    def test_category_auto_detected(self):
        """category가 자동 분류됨"""
        err = KisApiError("EGW00123", "test", "/test")
        assert err.category is not None

    def test_unknown_code_category_is_none(self):
        """모르는 코드는 category가 None"""
        err = KisApiError("XYZ99999", "test", "/test")
        assert err.category is None

    def test_str_representation(self):
        """str() 메서드가 정보 포함"""
        err = KisApiError("EGW00123", "auth failed", "/auth")
        s = str(err)
        assert "EGW00123" in s
        assert "auth failed" in s

    def test_specific_subclass_auth(self):
        """KisAuthError"""
        err = KisAuthError("EGW00123", "auth failed", "/auth")
        assert isinstance(err, KisApiError)

    def test_specific_subclass_rate_limit(self):
        """KisRateLimitError"""
        err = KisRateLimitError("EGW00212", "rate limit", "/api")
        assert isinstance(err, KisApiError)

    def test_specific_subclass_server(self):
        """KisServerError"""
        err = KisServerError("EGW00150", "server error", "/api")
        assert isinstance(err, KisApiError)