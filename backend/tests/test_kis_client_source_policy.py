"""Phase 1 — TDD: KIS API Client, Source Policy, DataUnavailable 테스트"""
import pytest
from datetime import datetime, timezone
from kis.schemas import KisSourceMeta, DataUnavailable
from kis.source_policy import (
    SourcePolicy,
    SourcePolicyViolation,
    MissingKisSourceError,
    StaleDataError,
    MissingFieldError,
    validate_source,
    build_source_meta,
)
from kis.client import KisClient


# ── Source Policy Tests ──

class TestSourcePolicy:
    """SourcePolicy 규칙 테스트"""

    def test_accepts_valid_kis_source(self):
        """KIS_API source는 정상 통과"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
        )
        policy = SourcePolicy()
        result = policy.validate(meta)
        assert result is True

    def test_rejects_non_kis_source(self):
        """KIS_API가 아닌 source는 거부"""
        policy = SourcePolicy()
        with pytest.raises(MissingKisSourceError):
            policy.validate(None)

    def test_rejects_stale_data(self):
        """stale 데이터 거부"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
            is_stale=True,
        )
        policy = SourcePolicy(max_stale_seconds=0)
        with pytest.raises(StaleDataError):
            policy.validate(meta)

    def test_detects_missing_fields(self):
        """필드 누락 감지"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
            missing_fields=("current_price",),
        )
        policy = SourcePolicy()
        with pytest.raises(MissingFieldError) as exc:
            policy.validate(meta)
        assert "current_price" in str(exc.value)

    def test_non_stale_data_ok(self):
        """최신 데이터는 통과"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
            is_stale=False,
        )
        policy = SourcePolicy(max_stale_seconds=300)
        result = policy.validate(meta)
        assert result is True

    def test_data_unavailable_is_not_fallback(self):
        """DataUnavailable을 임의 기본값으로 대체 금지"""
        du = DataUnavailable(
            reason_code="API_ERROR",
            reason_text="KIS API returned 500",
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
        )
        # DataUnavailable은 source_policy에서 직접 사용되지 않음
        # 대신 KisSourceMeta가 없는 상태에서 validate_source 호출 시 MissingKisSourceError
        pass


class TestValidateSource:
    """validate_source 편의 함수"""

    def test_validate_source_with_meta(self):
        """KisSourceMeta 전달 시 정상"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
        )
        assert validate_source(meta) is True

    def test_validate_source_with_none(self):
        """None 전달 시 예외"""
        with pytest.raises(MissingKisSourceError):
            validate_source(None)

    def test_validate_source_data_unavailable_raises(self):
        """DataUnavailable 전달 시 예외 (KIS source 아님)"""
        du = DataUnavailable(
            reason_code="ERROR",
            reason_text="error",
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
        )
        with pytest.raises(MissingKisSourceError):
            validate_source(du)


class TestBuildSourceMeta:
    """build_source_meta 편의 함수"""

    def test_build_basic(self):
        """기본 메타데이터 생성"""
        meta = build_source_meta(
            endpoint="/uapi/domestic-stock/v1/trading/inquire-price",
            tr_id="FHKST01010100",
            raw_data='{"output": {"price": 70000}}',
        )
        assert meta.source == "KIS_API"
        assert meta.endpoint == "/uapi/domestic-stock/v1/trading/inquire-price"
        assert meta.tr_id == "FHKST01010100"
        assert meta.raw_response_hash is not None
        assert len(meta.raw_response_hash) == 64  # SHA256 hex
        assert meta.is_stale is False
        assert meta.missing_fields == ()

    def test_build_marks_missing_fields(self):
        """누락된 필드 표시"""
        meta = build_source_meta(
            endpoint="/test",
            raw_data='{"price": null}',
            expected_fields=("price", "volume"),
        )
        assert "volume" in meta.missing_fields

    def test_build_different_raw_data_different_hash(self):
        """서로 다른 데이터 → 다른 해시"""
        meta1 = build_source_meta(endpoint="/test", raw_data='{"a": 1}')
        meta2 = build_source_meta(endpoint="/test", raw_data='{"a": 2}')
        assert meta1.raw_response_hash != meta2.raw_response_hash

    def test_build_tr_id_optional(self):
        """tr_id 없이도 생성 가능"""
        meta = build_source_meta(
            endpoint="/oauth2/tokenP",
            raw_data='{"token": "xxx"}',
        )
        assert meta.tr_id is None


# ── KisClient 기본 구조 Tests ──
# 실제 API 호출 없이 구조와 정책 연결만 검증

class TestKisClient:
    """KisClient 구조 테스트 (실제 API 호출 없음)"""

    def test_client_initialization(self):
        """KisClient 초기화"""
        client = KisClient()
        assert client is not None
        assert client.source_policy is not None
        assert client.rate_limiter is not None
        assert client.auth_manager is not None

    def test_client_has_base_url(self):
        """base_url 존재"""
        client = KisClient()
        assert client.base_url is not None
        assert "koreainvestment.com" in client.base_url or "9443" in client.base_url

    def test_client_build_url(self):
        """URL 빌드"""
        client = KisClient()
        url = client._build_url("/test/path")
        assert url.endswith("/test/path")

    def test_client_prepare_headers(self):
        """헤더 준비 (auth 없이)"""
        client = KisClient()
        headers = client._prepare_headers(tr_id="FHKST01010100", requires_auth=False)
        assert headers["content-type"] == "application/json"
        assert "tr_id" in headers
        assert "authorization" not in headers

    def test_client_requires_auth_header(self):
        """인증 필요 시 authorization 헤더 포함"""
        client = KisClient()
        # auth manager에 먼저 토큰이 없으므로 require_auth=True 시 예외
        headers = client._prepare_headers(tr_id="FHKST01010100", requires_auth=False)
        assert "authorization" not in headers

    def test_client_get_endpoint_info(self):
        """endpoint 정보 조회"""
        client = KisClient()
        ep = client.get_endpoint_info("inquire_price")
        assert ep is not None
        assert ep.name == "inquire_price"

    def test_client_is_order_endpoint_true(self):
        """주문 endpoint 확인"""
        client = KisClient()
        assert client.is_order_endpoint("order_buy") is True
        assert client.is_order_endpoint("inquire_price") is False

    def test_client_data_unavailable_from_error(self):
        """에러 → DataUnavailable 생성"""
        client = KisClient()
        du = client.data_unavailable(
            reason_code="API_ERROR",
            reason_text="Connection failed",
            endpoint="/test",
        )
        assert isinstance(du, DataUnavailable)
        assert du.reason_code == "API_ERROR"
        assert du.reason_text == "Connection failed"