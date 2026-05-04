"""Phase 1 — TDD: KisSourceMeta, DataUnavailable 테스트"""
import pytest
from datetime import datetime, timezone
from kis.schemas import KisSourceMeta, DataUnavailable


class TestKisSourceMeta:
    def test_source_is_kis_api(self):
        """KisSourceMeta 생성 시 source가 KIS_API로 고정되는지"""
        meta = KisSourceMeta(
            endpoint="/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id="TTTC8434R",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc123",
            request_id="req-001",
        )
        assert meta.source == "KIS_API"

    def test_default_is_stale_false(self):
        """is_stale 기본값이 False인지"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
        )
        assert meta.is_stale is False

    def test_default_missing_fields_empty(self):
        """missing_fields 기본값이 빈 튜플인지"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
        )
        assert meta.missing_fields == ()

    def test_frozen_dataclass(self):
        """KisSourceMeta가 frozen dataclass여서 수정 불가"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
        )
        with pytest.raises(AttributeError):
            meta.source = "OTHER"  # type: ignore[misc]

    def test_stale_flag_settable_at_init(self):
        """생성 시 is_stale=True로 설정 가능"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
            is_stale=True,
        )
        assert meta.is_stale is True

    def test_missing_fields_settable_at_init(self):
        """생성 시 missing_fields 지정 가능"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
            missing_fields=("current_price", "volume"),
        )
        assert meta.missing_fields == ("current_price", "volume")

    def test_tr_id_optional(self):
        """tr_id가 None일 수 있음"""
        meta = KisSourceMeta(
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            raw_response_hash="abc",
            request_id="req-001",
            tr_id=None,
        )
        assert meta.tr_id is None


class TestDataUnavailable:
    def test_basic_creation(self):
        """DataUnavailable 기본 생성"""
        now = datetime.now(timezone.utc)
        du = DataUnavailable(
            reason_code="API_ERROR",
            reason_text="KIS API returned 500",
            endpoint="/uapi/domestic-stock/v1/trading/inquire-price",
            fetched_at=now,
        )
        assert du.reason_code == "API_ERROR"
        assert du.reason_text == "KIS API returned 500"
        assert du.endpoint == "/uapi/domestic-stock/v1/trading/inquire-price"
        assert du.fetched_at == now

    def test_request_id_optional(self):
        """request_id가 None일 수 있음"""
        du = DataUnavailable(
            reason_code="TIMEOUT",
            reason_text="Request timed out",
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
        )
        assert du.request_id is None

    def test_request_id_provided(self):
        """request_id 명시적 전달"""
        du = DataUnavailable(
            reason_code="TIMEOUT",
            reason_text="Request timed out",
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
            request_id="req-001",
        )
        assert du.request_id == "req-001"

    def test_frozen_dataclass(self):
        """DataUnavailable가 frozen dataclass여서 수정 불가"""
        du = DataUnavailable(
            reason_code="ERROR",
            reason_text="error",
            endpoint="/test",
            fetched_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            du.reason_code = "OTHER"  # type: ignore[misc]