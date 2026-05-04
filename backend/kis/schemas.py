"""KIS API Gateway Schemas

SAT3의 모든 KIS API 호출 결과를 표현하는 데이터클래스.
- KisSourceMeta: 모든 API 응답에 출처 메타데이터 부여
- DataUnavailable: API 실패 또는 데이터 누락 시 사용 (추정값 생성 금지)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Tuple


@dataclass(frozen=True)
class KisSourceMeta:
    """KIS API 응답 출처 메타데이터

    모든 KIS API 응답을 이 구조에 래핑하여 출처 추적성을 확보.
    KIS_API 외부 출처는 source_policy에서 거부됨.

    Attributes:
        source: 항상 "KIS_API"로 고정
        endpoint: KIS API 엔드포인트 경로
        tr_id: KIS TR ID (조회/주문 식별자, None 가능)
        fetched_at: 데이터 조회 시각 (UTC)
        raw_response_hash: 원본 응답 SHA256 해시 (데이터 무결성)
        request_id: 요청 식별자 (UUID, 추적용)
        is_stale: 데이터가 오래되었는지 여부 (기본 False)
        missing_fields: 응답에서 누락된 필드 목록 (기본 빈 튜플)
    """
    endpoint: str
    fetched_at: datetime
    raw_response_hash: str
    request_id: str
    source: Literal["KIS_API"] = field(default="KIS_API", init=True)
    tr_id: str | None = None
    is_stale: bool = False
    missing_fields: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DataUnavailable:
    """API 실패 또는 데이터 누락을 표현하는 타입

    API 실패 시 추정값을 절대 생성하지 않고 이 타입을 반환.
    이후 Phase의 Consumer는 DataUnavailable을 만나면 해당 항목을
    평가 불가 처리하거나 건너뛰어야 함.

    Attributes:
        reason_code: 실패 원인 코드 (예: API_ERROR, TIMEOUT, MISSING_FIELD)
        reason_text: 사람이 읽을 수 있는 실패 설명
        endpoint: 실패가 발생한 API 엔드포인트
        fetched_at: 실패 시각 (UTC)
        request_id: 실패 요청 식별자 (선택)
    """
    reason_code: str
    reason_text: str
    endpoint: str
    fetched_at: datetime
    request_id: str | None = None