"""KIS API Endpoint Catalog

한국투자증권 Open API의 모든 endpoint를 한 곳에서 정의한다.
하드코딩된 URL 문자열이 프로젝트 곳곳에 흩어지는 것을 방지한다.

Phase 1 범위: endpoint catalog / resolver 수준까지만 구현.
주문 endpoint는 식별 가능하도록 is_order_endpoint=True로 표시하지만,
주문 실행 로직은 이후 Phase에서 구현한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class EndpointCategory(Enum):
    """KIS API Endpoint 영역 분류"""
    OAUTH = "oauth"
    ORDER_ACCOUNT = "order_account"
    MARKET_PRICE = "market_price"
    SECTOR = "sector"
    STOCK_INFO = "stock_info"
    MARKET_ANALYSIS = "market_analysis"
    RANKING = "ranking"
    REALTIME = "realtime"


class EndpointNotFoundError(Exception):
    """요청한 endpoint name을 카탈로그에서 찾을 수 없음"""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Endpoint not found in catalog: {name!r}")


@dataclass(frozen=True)
class KisEndpoint:
    """KIS API Endpoint 정의

    Attributes:
        name: 고유 식별자
        category: API 영역 분류
        path: API 경로
        method: HTTP 메서드 (GET/POST)
        tr_id: KIS TR ID (선택, None 가능)
        requires_auth: 인증 필요 여부
        is_order_endpoint: 실제 주문 endpoint 여부
        data_source: 항상 "KIS_API" (고정)
        description: 설명
    """
    name: str
    category: EndpointCategory
    path: str
    method: Literal["GET", "POST"]
    tr_id: str | None = None
    requires_auth: bool = True
    is_order_endpoint: bool = False
    data_source: Literal["KIS_API"] = field(default="KIS_API", init=False)
    description: str = ""


# ── Endpoint Catalog ──
# 모든 KIS API endpoint를 한 곳에서 관리
# format: (name, category, path, method, tr_id, requires_auth, is_order_endpoint, description)

_ENDPOINT_DEFS: list[tuple] = [
    # ── OAuth / 인증 ──
    ("oauth_token", EndpointCategory.OAUTH, "/oauth2/tokenP", "POST", None, False, False, "OAuth Access Token 발급"),
    ("oauth_revoke", EndpointCategory.OAUTH, "/oauth2/revokeP", "POST", None, True, False, "Access Token 폐기"),

    # ── 국내주식 주문/계좌 ──
    ("order_buy", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/order-cash", "POST", "TTTC0802U", True, True, "현금매수 주문"),
    ("order_sell", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/order-cash", "POST", "TTTC0801U", True, True, "현금매도 주문"),
    ("order_modify", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/order-rvsecncl", "POST", "TTTC0803U", True, True, "정정취소 주문"),
    ("inquire_balance", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/inquire-balance", "GET", "TTTC8434R", True, False, "계좌 잔고 조회"),
    ("inquire_psbl_order", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/inquire-psbl-order", "GET", "TTTC8908R", True, False, "매수 가능 조회"),
    ("inquire_ccnl", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/inquire-ccnl", "GET", "TTTC8001R", True, False, "주문 체결 내역 조회"),
    ("inquire_profit", EndpointCategory.ORDER_ACCOUNT, "/uapi/domestic-stock/v1/trading/inquire-profit", "GET", "TTTC8504R", True, False, "실현 손익 조회"),

    # ── 국내주식 기본시세 ──
    ("inquire_price", EndpointCategory.MARKET_PRICE, "/uapi/domestic-stock/v1/quotations/inquire-price", "GET", "FHKST01010100", True, False, "주식 현재가 시세"),
    ("inquire_asking_price", EndpointCategory.MARKET_PRICE, "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn", "GET", "FHKST01010200", True, False, "호가/예상체결가"),
    ("inquire_day_period_price", EndpointCategory.MARKET_PRICE, "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "GET", "FHKST03010100", True, False, "기간별 시세 (일봉)"),
    ("inquire_minute_period_price", EndpointCategory.MARKET_PRICE, "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice", "GET", "FHKST03010200", True, False, "시간별 시세 (분봉)"),
    ("inquire_time_ccnl", EndpointCategory.MARKET_PRICE, "/uapi/domestic-stock/v1/quotations/inquire-time-ccnl", "GET", "FHKST01010300", True, False, "시간대별 체결가"),

    # ── 국내주식 업종/기타 ──
    ("inquire_sector_index", EndpointCategory.SECTOR, "/uapi/domestic-stock/v1/quotations/inquire-index", "GET", "FHPUP02100000", True, False, "업종 현재 지수"),
    ("inquire_sector_daily", EndpointCategory.SECTOR, "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice", "GET", "FHPUP02110000", True, False, "업종 일자별 지수"),
    ("inquire_sector_time", EndpointCategory.SECTOR, "/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice", "GET", "FHPUP02120000", True, False, "업종 시간별 지수"),
    ("inquire_holiday", EndpointCategory.SECTOR, "/uapi/domestic-stock/v1/quotations/inquire-holiday", "GET", "FHKST01010900", True, False, "국내 휴장일 조회"),

    # ── 국내주식 종목정보 ──
    ("inquire_product_basic", EndpointCategory.STOCK_INFO, "/uapi/domestic-stock/v1/quotations/search-product-info", "GET", "CTPF1002R", True, False, "상품 기본 조회"),
    ("inquire_stock_basic", EndpointCategory.STOCK_INFO, "/uapi/domestic-stock/v1/quotations/inquire-stock-basic-info", "GET", "FHKST01010600", True, False, "주식 기본 조회"),
    ("inquire_financial_ratio", EndpointCategory.STOCK_INFO, "/uapi/domestic-stock/v1/quotations/inquire-financial-ratio", "GET", "FHKST66410000", True, False, "재무 비율 조회"),

    # ── 시세분석 ──
    ("inquire_trading_volume", EndpointCategory.MARKET_ANALYSIS, "/uapi/domestic-stock/v1/quotations/volume-rank", "GET", "FHPST01710000", True, False, "거래량 순위"),
    ("inquire_volatility", EndpointCategory.MARKET_ANALYSIS, "/uapi/domestic-stock/v1/quotations/inquire-price-volatility", "GET", "FHPST02100000", True, False, "변동성 완화장치 현황"),

    # ── 순위분석 ──
    ("inquire_rank_fluctuation", EndpointCategory.RANKING, "/uapi/domestic-stock/v1/ranking/fluctuation", "GET", "FHPST01800000", True, False, "등락률 순위"),
    ("inquire_rank_market_cap", EndpointCategory.RANKING, "/uapi/domestic-stock/v1/ranking/market-cap", "GET", "FHPST02130000", True, False, "시가총액 순위"),
    ("inquire_rank_investor", EndpointCategory.RANKING, "/uapi/domestic-stock/v1/ranking/investor", "GET", "FHPST02140000", True, False, "투자자별 매매 동향"),
    ("inquire_rank_short_selling", EndpointCategory.RANKING, "/uapi/domestic-stock/v1/ranking/short-selling", "GET", "FHPST02200000", True, False, "공매도 순위"),

    # ── 실시간시세 ──
    # WebSocket approval key (KIS uses capital 'A' in /oauth2/Approval)
    ("realtime_websocket", EndpointCategory.REALTIME, "/oauth2/Approval", "POST", None, True, False, "실시간 웹소켓 승인 키 발급"),
]

# 빌드: tuple → KisEndpoint
ENDPOINT_CATALOG: list[KisEndpoint] = []
for defs in _ENDPOINT_DEFS:
    name, category, path, method, tr_id, requires_auth, is_order, desc = defs
    ENDPOINT_CATALOG.append(KisEndpoint(
        name=name, category=category, path=path, method=method,
        tr_id=tr_id, requires_auth=requires_auth,
        is_order_endpoint=is_order, description=desc,
    ))

# name → KisEndpoint lookup
_ENDPOINT_MAP: dict[str, KisEndpoint] = {ep.name: ep for ep in ENDPOINT_CATALOG}

# 편의 alias
_ENDPOINT_ALIASES = {
    "domestic_stock_current_price": "inquire_price",
    "domestic_stock_orderbook": "inquire_asking_price",
    "domestic_holiday": "inquire_holiday",
    "domestic_stock_basic_info": "inquire_stock_basic",
    "domestic_stock_execution": "inquire_time_ccnl",

    # WebSocket approval endpoint aliases
    "websocket_approval": "realtime_websocket",
    "realtime_websocket_approval": "realtime_websocket",
}


def get_endpoint(name: str) -> KisEndpoint:
    """endpoint name으로 KisEndpoint 조회

    Args:
        name: endpoint 식별자 (예: "inquire_price", "order_buy")

    Returns:
        KisEndpoint 객체

    Raises:
        EndpointNotFoundError: name을 찾을 수 없는 경우
    """
    ep = _ENDPOINT_MAP.get(name) or _ENDPOINT_MAP.get(_ENDPOINT_ALIASES.get(name, ""))
    if ep is None:
        raise EndpointNotFoundError(name)
    return ep


def list_endpoints_by_category(category: EndpointCategory) -> list[KisEndpoint]:
    """특정 카테고리의 모든 endpoint 목록 반환

    Args:
        category: 조회할 EndpointCategory

    Returns:
        해당 카테고리의 KisEndpoint 목록
    """
    return [ep for ep in ENDPOINT_CATALOG if ep.category == category]


def is_order_endpoint(name: str) -> bool:
    """endpoint name이 주문 endpoint인지 확인

    Args:
        name: endpoint 식별자

    Returns:
        주문 endpoint면 True
    """
    try:
        ep = get_endpoint(name)
        return ep.is_order_endpoint
    except EndpointNotFoundError:
        return False