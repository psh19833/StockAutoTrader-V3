"""KIS Source Policy — 데이터 출처 검증

SAT3의 절대 원칙:
- 모든 데이터는 KIS_API source metadata를 가져야 한다.
- KIS 외부에서 온 데이터는 거부한다.
- Stale 데이터는 경고 또는 거부한다.
- Missing field 데이터는 별도 처리한다.
- DataUnavailable을 임의 기본값으로 대체하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from kis.schemas import KisSourceMeta, DataUnavailable


class SourcePolicyViolation(Exception):
    """Source Policy 위반"""
    pass


class MissingKisSourceError(SourcePolicyViolation):
    """KIS_API 출처가 없는 데이터"""
    def __init__(self, detail: str = "Data missing KIS_API source metadata"):
        super().__init__(detail)


class StaleDataError(SourcePolicyViolation):
    """Stale 데이터 사용 시도"""
    def __init__(self, detail: str = "Data is stale"):
        super().__init__(detail)


class MissingFieldError(SourcePolicyViolation):
    """필수 필드 누락"""
    def __init__(self, fields: tuple[str, ...]):
        self.fields = fields
        super().__init__(f"Missing required fields: {', '.join(fields)}")


class SourcePolicy:
    """KIS API Source Policy 검증기

    모든 데이터는 KIS API Gateway를 통해 KIS_API source metadata를
    부여받아야 하며, 이 policy가 이를 검증한다.
    """

    def __init__(self, max_stale_seconds: int = 300):
        """
        Args:
            max_stale_seconds: 데이터가 유효한 최대 경과 시간 (초)
        """
        self._max_stale_seconds = max_stale_seconds

    def validate(self, meta: KisSourceMeta | None) -> bool:
        """Source Metadata 검증

        Args:
            meta: KisSourceMeta 객체 또는 None

        Returns:
            검증 통과 시 True

        Raises:
            MissingKisSourceError: meta가 None이거나 KIS source가 아님
            StaleDataError: 데이터가 오래됨
            MissingFieldError: 필수 필드 누락
        """
        if meta is None:
            raise MissingKisSourceError("No source metadata provided")

        if meta.source != "KIS_API":
            raise MissingKisSourceError(
                f"Invalid source: {meta.source}. Expected KIS_API"
            )

        if meta.is_stale:
            raise StaleDataError(
                f"Data is stale (fetched_at={meta.fetched_at}, "
                f"max_stale={self._max_stale_seconds}s)"
            )

        # 실제 경과 시간 기준 stale 체크
        elapsed = (datetime.now(timezone.utc) - meta.fetched_at).total_seconds()
        if elapsed > self._max_stale_seconds:
            raise StaleDataError(
                f"Data age ({elapsed:.0f}s) exceeds max_stale ({self._max_stale_seconds}s)"
            )

        if meta.missing_fields:
            raise MissingFieldError(meta.missing_fields)

        return True


def validate_source(meta: KisSourceMeta | DataUnavailable | None) -> bool:
    """Source Metadata 검증 편의 함수

    Args:
        meta: KisSourceMeta, DataUnavailable, 또는 None

    Returns:
        검증 통과 시 True

    Raises:
        MissingKisSourceError: 유효한 KIS source가 아님
        StaleDataError: 데이터가 오래됨
        MissingFieldError: 필수 필드 누락
    """
    if meta is None:
        raise MissingKisSourceError("No source metadata provided")
    if isinstance(meta, DataUnavailable):
        raise MissingKisSourceError(
            f"DataUnavailable cannot be used as source: "
            f"[{meta.reason_code}] {meta.reason_text}"
        )
    if not isinstance(meta, KisSourceMeta):
        raise MissingKisSourceError(f"Unknown metadata type: {type(meta).__name__}")

    policy = SourcePolicy()
    return policy.validate(meta)


def build_source_meta(
    endpoint: str,
    raw_data: str,
    tr_id: str | None = None,
    request_id: str | None = None,
    expected_fields: tuple[str, ...] = (),
) -> KisSourceMeta:
    """KisSourceMeta 생성 편의 함수

    API 응답으로부터 source metadata를 생성한다.

    Args:
        endpoint: API 엔드포인트 경로
        raw_data: 원본 응답 문자열 (JSON)
        tr_id: KIS TR ID (선택)
        request_id: 요청 식별자 (선택, 미지정 시 자동 생성)
        expected_fields: 검증이 필요한 필드 목록

    Returns:
        KisSourceMeta 객체
    """
    raw_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    # 누락된 필드 확인
    missing: list[str] = []
    if expected_fields:
        try:
            parsed = json.loads(raw_data)
            for field in expected_fields:
                value = parsed
                for key in field.split("."):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
                if value is None:
                    missing.append(field)
        except (json.JSONDecodeError, TypeError):
            missing = list(expected_fields)

    return KisSourceMeta(
        endpoint=endpoint,
        tr_id=tr_id,
        fetched_at=datetime.now(timezone.utc),
        raw_response_hash=raw_hash,
        request_id=request_id or hashlib.md5(
            f"{endpoint}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12],
        is_stale=False,
        missing_fields=tuple(missing),
    )