"""Phase 1 — TDD: KIS API Endpoint Catalog 테스트"""
import pytest
from kis.endpoints import (
    KisEndpoint,
    EndpointCategory,
    EndpointNotFoundError,
    ENDPOINT_CATALOG,
    get_endpoint,
    list_endpoints_by_category,
    is_order_endpoint,
)


class TestEndpointCategory:
    """EndpointCategory Enum"""

    def test_categories_exist(self):
        """필수 카테고리 존재"""
        assert EndpointCategory.OAUTH
        assert EndpointCategory.ORDER_ACCOUNT
        assert EndpointCategory.MARKET_PRICE
        assert EndpointCategory.SECTOR
        assert EndpointCategory.STOCK_INFO
        assert EndpointCategory.MARKET_ANALYSIS
        assert EndpointCategory.RANKING
        assert EndpointCategory.REALTIME

    def test_all_categories_have_values(self):
        """모든 카테고리가 value를 가짐"""
        for cat in EndpointCategory:
            assert isinstance(cat.value, str)
            assert len(cat.value) > 0


class TestKisEndpoint:
    """KisEndpoint 데이터클래스"""

    def test_has_all_required_fields(self):
        """필수 필드 존재"""
        ep = KisEndpoint(
            name="test",
            category=EndpointCategory.OAUTH,
            path="/oauth2/tokenP",
            method="POST",
            tr_id=None,
            requires_auth=False,
            is_order_endpoint=False,
            description="Test endpoint",
        )
        assert ep.name == "test"
        assert ep.category == EndpointCategory.OAUTH
        assert ep.path == "/oauth2/tokenP"
        assert ep.method == "POST"
        assert ep.tr_id is None
        assert ep.requires_auth is False
        assert ep.is_order_endpoint is False
        assert ep.data_source == "KIS_API"
        assert ep.description == "Test endpoint"

    def test_data_source_is_always_kis_api(self):
        """data_source는 항상 KIS_API"""
        ep = KisEndpoint(
            name="test",
            category=EndpointCategory.OAUTH,
            path="/test",
            method="GET",
            tr_id=None,
            requires_auth=False,
            is_order_endpoint=False,
            description="test",
        )
        assert ep.data_source == "KIS_API"


class TestEndpointCatalog:
    """ENDPOINT_CATALOG"""

    def test_catalog_not_empty(self):
        """카탈로그가 비어있지 않음"""
        assert len(ENDPOINT_CATALOG) > 0

    def test_all_endpoints_have_unique_names(self):
        """모든 endpoint name이 고유"""
        names = [ep.name for ep in ENDPOINT_CATALOG]
        assert len(names) == len(set(names))

    def test_oauth_token_endpoint(self):
        """OAuth 토큰 발급 엔드포인트"""
        ep = get_endpoint("oauth_token")
        assert ep is not None
        assert ep.category == EndpointCategory.OAUTH
        assert ep.path == "/oauth2/tokenP"
        assert ep.method == "POST"
        assert ep.requires_auth is False

    def test_inquire_balance_endpoint(self):
        """잔고 조회 엔드포인트"""
        ep = get_endpoint("inquire_balance")
        assert ep is not None
        assert ep.category == EndpointCategory.ORDER_ACCOUNT
        assert ep.method == "GET"
        assert ep.requires_auth is True

    def test_inquire_price_endpoint(self):
        """현재가 조회 엔드포인트"""
        ep = get_endpoint("inquire_price")
        assert ep is not None
        assert ep.category == EndpointCategory.MARKET_PRICE
        assert ep.method == "GET"
        assert ep.requires_auth is True

    def test_realtime_websocket_endpoint(self):
        """실시간 웹소켓 엔드포인트"""
        ep = get_endpoint("realtime_websocket")
        assert ep is not None
        assert ep.category == EndpointCategory.REALTIME
        assert ep.requires_auth is True

    def test_order_buy_endpoint(self):
        """매수 주문 엔드포인트 — 식별 가능해야 함"""
        ep = get_endpoint("order_buy")
        assert ep is not None
        assert ep.category == EndpointCategory.ORDER_ACCOUNT
        assert ep.is_order_endpoint is True
        assert ep.method == "POST"

    def test_order_sell_endpoint(self):
        """매도 주문 엔드포인트 — 식별 가능해야 함"""
        ep = get_endpoint("order_sell")
        assert ep is not None
        assert ep.category == EndpointCategory.ORDER_ACCOUNT
        assert ep.is_order_endpoint is True
        assert ep.method == "POST"


class TestGetEndpoint:
    """get_endpoint 함수"""

    def test_known_name_returns_endpoint(self):
        """알려진 name → KisEndpoint 반환"""
        ep = get_endpoint("oauth_token")
        assert isinstance(ep, KisEndpoint)

    def test_unknown_name_raises_error(self):
        """모르는 name → EndpointNotFoundError"""
        with pytest.raises(EndpointNotFoundError) as exc:
            get_endpoint("non_existent_endpoint")
        assert "non_existent_endpoint" in str(exc.value)

    def test_case_sensitive(self):
        """대소문자 구분"""
        with pytest.raises(EndpointNotFoundError):
            get_endpoint("OAuth_Token")


class TestListEndpointsByCategory:
    """list_endpoints_by_category 함수"""

    def test_oauth_category_returns_endpoints(self):
        """OAuth 카테고리 목록"""
        eps = list_endpoints_by_category(EndpointCategory.OAUTH)
        assert len(eps) > 0
        assert all(ep.category == EndpointCategory.OAUTH for ep in eps)

    def test_actual_order_endpoints_found(self):
        """ORDER_ACCOUNT 카테고리 결과"""
        eps = list_endpoints_by_category(EndpointCategory.ORDER_ACCOUNT)
        assert len(eps) > 0
        assert all(ep.category == EndpointCategory.ORDER_ACCOUNT for ep in eps)


class TestIsOrderEndpoint:
    """is_order_endpoint 함수"""

    def test_order_buy_is_order(self):
        """매수 주문 → True"""
        assert is_order_endpoint("order_buy") is True

    def test_order_sell_is_order(self):
        """매도 주문 → True"""
        assert is_order_endpoint("order_sell") is True

    def test_oauth_is_not_order(self):
        """인증 → False"""
        assert is_order_endpoint("oauth_token") is False

    def test_inquire_price_is_not_order(self):
        """시세 조회 → False"""
        assert is_order_endpoint("inquire_price") is False


class TestEndpointPaths:
    """endpoint path/tr_id 검증"""

    def test_all_endpoints_have_valid_methods(self):
        """모든 endpoint method가 GET/POST"""
        valid = {"GET", "POST"}
        for ep in ENDPOINT_CATALOG:
            assert ep.method in valid, f"{ep.name} has invalid method {ep.method}"

    def test_all_endpoints_have_path(self):
        """모든 endpoint가 path를 가짐"""
        for ep in ENDPOINT_CATALOG:
            assert ep.path.startswith("/"), f"{ep.name} path must start with /"

    def test_auth_required_endpoints_have_tr_id_or_none(self):
        """인증 필요한 endpoint는 tr_id가 있거나 None"""
        for ep in ENDPOINT_CATALOG:
            if ep.requires_auth and ep.category != EndpointCategory.REALTIME:
                # 실제 API endpoint는 tr_id가 있거나 OAuth처럼 없을 수 있음
                assert ep.tr_id is None or len(ep.tr_id) > 0

    def test_order_endpoints_marked_correctly(self):
        """주문 endpoint만 is_order_endpoint=True"""
        for ep in ENDPOINT_CATALOG:
            if ep.is_order_endpoint:
                assert ep.method == "POST"
                assert ep.requires_auth is True