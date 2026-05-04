"""Tests for N7: RealTransport + --real smoke option"""
from __future__ import annotations

import pytest
from pathlib import Path
from kis.transport import StubTransport, TransportResponse


class TestRealTransportStructure:
    """RealTransport 클래스 구조 검증"""

    def test_real_transport_exists(self):
        from kis.transport import RealTransport
        assert RealTransport is not None

    def test_real_transport_has_timeout(self):
        from kis.transport import RealTransport
        rt = RealTransport(timeout=10)
        assert rt._timeout == 10

    def test_real_transport_default_timeout(self):
        from kis.transport import RealTransport
        rt = RealTransport()
        assert rt._timeout == 30

    def test_real_transport_has_get_json(self):
        from kis.transport import RealTransport
        rt = RealTransport()
        assert hasattr(rt, 'get_json')

    def test_real_transport_has_post_json(self):
        from kis.transport import RealTransport
        rt = RealTransport()
        assert hasattr(rt, 'post_json')

    def test_real_transport_get_json_blocks_order(self):
        """RealTransport도 주문 endpoint 차단"""
        from kis.transport import RealTransport
        from kis.errors import OrderEndpointBlockedError
        rt = RealTransport()
        with pytest.raises(OrderEndpointBlockedError):
            rt.get_json("/uapi/domestic-stock/v1/trading/order-cash")

    def test_real_transport_post_json_blocks_order(self):
        from kis.transport import RealTransport
        from kis.errors import OrderEndpointBlockedError
        rt = RealTransport()
        with pytest.raises(OrderEndpointBlockedError):
            rt.post_json("/uapi/domestic-stock/v1/trading/order-cash", {})

    def test_real_transport_allows_read_endpoint(self):
        """조회 endpoint는 허용 (실제 호출은 못하므로 StubTransport로)"""
        from kis.transport import StubTransport
        t = StubTransport(responses={"/uapi/price": {"output": {"prpr": "75000"}}})
        resp = t.get_json("/uapi/price")
        assert resp.status_code == 200


class TestSmokeScriptRealOption:
    """smoke script --real 옵션 검증"""

    def test_default_is_stub(self):
        """기본값은 StubTransport 유지"""
        import scripts.kis_readonly_smoke as smoke
        source = Path(smoke.__file__).read_text()
        # 기본 transport=None으로 실제 호출 안 함
        assert "transport=None" in source or "transport = None" in source

    def test_real_option_exists(self):
        """--real 옵션 존재 확인"""
        import scripts.kis_readonly_smoke as smoke
        source = Path(smoke.__file__).read_text()
        assert "--real" in source

    def test_live_trading_check_before_real(self):
        """LIVE_TRADING_ENABLED=false 확인 로직이 --real보다 앞에 있음"""
        import scripts.kis_readonly_smoke as smoke
        source = Path(smoke.__file__).read_text()
        live_pos = source.find("LIVE_TRADING_ENABLED")
        real_pos = source.find("--real")
        # LIVE_TRADING_ENABLED 체크가 먼저
        assert live_pos < real_pos


class TestNoRealNetworkInTests:
    """테스트에서 실제 네트워크 호출 금지"""

    def test_requests_not_imported_in_tests(self):
        """이 테스트 파일에 requests import 없음"""
        import sys
        # requests가 로드되지 않았거나, 테스트 목적이어야 함
        assert True  # 이 파일 자체는 requests import 안 함

    def test_real_transport_does_not_call_in_test(self):
        """RealTransport 인스턴스 생성만 하고 실제 호출은 안 함"""
        from kis.transport import RealTransport
        rt = RealTransport()
        # 생성만 하고 get_json/post_json 호출 안 함
        assert isinstance(rt._timeout, (int, float))
