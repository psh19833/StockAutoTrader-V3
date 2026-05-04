"""KIS API 에러 코드 매핑 및 예외 클래스

KIS API 응답의 에러 코드를 분류하고 적절한 예외를 발생시킨다.
SAT3에서는 KIS API 오류를 추정값으로 대체하지 않고 항상 예외로 전파한다.
"""
from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class KisErrorCategory(Enum):
    """KIS API 에러 분류"""
    AUTH = "AUTH"                 # 인증 오류 (토큰 만료, 키 오류)
    RATE_LIMIT = "RATE_LIMIT"     # 호출 제한 초과
    INVALID_PARAM = "INVALID_PARAM"  # 잘못된 파라미터
    SERVER = "SERVER"             # KIS 서버 오류 (5xx)
    NOT_FOUND = "NOT_FOUND"       # 데이터 없음
    TRADE_FAIL = "TRADE_FAIL"     # 주문/거래 실패
    UNKNOWN = "UNKNOWN"           # 기타/미분류


class ErrorCodeInfo(NamedTuple):
    """에러 코드 정보"""
    category: KisErrorCategory
    message: str


# KIS API 공식 에러 코드 매핑 (주요 코드만 포함)
KIS_ERROR_CODES: dict[str, ErrorCodeInfo] = {
    # ── 인증 오류 ──
    "EGW00123": ErrorCodeInfo(KisErrorCategory.AUTH, "인증 실패 - API 키 또는 시크릿 오류"),
    "EGW00124": ErrorCodeInfo(KisErrorCategory.AUTH, "토큰 만료 - 재발급 필요"),
    "EGW00125": ErrorCodeInfo(KisErrorCategory.AUTH, "유효하지 않은 토큰"),
    "EGW00126": ErrorCodeInfo(KisErrorCategory.AUTH, "계좌번호 불일치"),

    # ── Rate Limit ──
    "EGW00212": ErrorCodeInfo(KisErrorCategory.RATE_LIMIT, "초당 호출 횟수 초과"),
    "EGW00213": ErrorCodeInfo(KisErrorCategory.RATE_LIMIT, "일일 호출 한도 초과"),

    # ── 파라미터 오류 ──
    "EGW00101": ErrorCodeInfo(KisErrorCategory.INVALID_PARAM, "필수 파라미터 누락"),
    "EGW00102": ErrorCodeInfo(KisErrorCategory.INVALID_PARAM, "잘못된 파라미터 형식"),
    "EGW00105": ErrorCodeInfo(KisErrorCategory.INVALID_PARAM, "유효하지 않은 TR ID"),
    "EGW00108": ErrorCodeInfo(KisErrorCategory.INVALID_PARAM, "유효하지 않은 종목코드"),

    # ── 서버 오류 ──
    "EGW00150": ErrorCodeInfo(KisErrorCategory.SERVER, "내부 서버 오류"),
    "EGW00151": ErrorCodeInfo(KisErrorCategory.SERVER, "서버 타임아웃"),
    "EGW00153": ErrorCodeInfo(KisErrorCategory.SERVER, "서버 점검 중"),

    # ── 데이터 없음 ──
    "EGW00201": ErrorCodeInfo(KisErrorCategory.NOT_FOUND, "조회 결과 없음"),
    "EGW00202": ErrorCodeInfo(KisErrorCategory.NOT_FOUND, "존재하지 않는 종목"),

    # ── 거래 실패 ──
    "EGW00301": ErrorCodeInfo(KisErrorCategory.TRADE_FAIL, "주문 가능 수량 초과"),
    "EGW00302": ErrorCodeInfo(KisErrorCategory.TRADE_FAIL, "예수금 부족"),
    "EGW00303": ErrorCodeInfo(KisErrorCategory.TRADE_FAIL, "주문 가격 제한 초과"),
    "EGW00305": ErrorCodeInfo(KisErrorCategory.TRADE_FAIL, "장시간 아님"),
    "EGW00310": ErrorCodeInfo(KisErrorCategory.TRADE_FAIL, "정리매매 종목"),
}


def classify_kis_error(error_code: str) -> ErrorCodeInfo | None:
    """KIS API 에러 코드 분류

    Args:
        error_code: KIS API 응답의 error_code 문자열

    Returns:
        ErrorCodeInfo 또는 알 수 없는 코드면 None
    """
    return KIS_ERROR_CODES.get(error_code)


class KisApiError(Exception):
    """KIS API 호출 실패 시 발생하는 기본 예외

    추정값을 생성하지 않고 이 예외를 발생시켜 호출자에게 실패를 전파한다.
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        endpoint: str,
    ):
        self.error_code = error_code
        self.message_text = message
        self.endpoint = endpoint
        info = classify_kis_error(error_code)
        self.category = info.category if info else None
        super().__init__(self._format())

    def _format(self) -> str:
        return (
            f"[{self.error_code}] {self.message_text} "
            f"(endpoint={self.endpoint}, category={self.category})"
        )

    def __str__(self) -> str:
        return self._format()


class KisAuthError(KisApiError):
    """KIS 인증 오류"""
    pass


class KisRateLimitError(KisApiError):
    """KIS Rate Limit 초과"""
    pass


class KisServerError(KisApiError):
    """KIS 서버 오류"""
    pass


class NetworkError(Exception):
    """네트워크 연결 오류"""
    pass


class TimeoutError(Exception):
    """요청 시간 초과"""
    pass


class OrderEndpointBlockedError(Exception):
    """주문 endpoint 호출 차단"""
    pass