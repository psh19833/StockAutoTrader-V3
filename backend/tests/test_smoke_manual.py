"""Tests for N6-MANUAL: Smoke script + .env.example + docs"""
from __future__ import annotations

import pytest
import os
from pathlib import Path


class TestEnvExample:
    """검증: .env.example 필수 변수 존재"""

    def _read_example(self) -> str:
        path = Path("/home/psh19/StockAutoTrader-V3/.env.example")
        if not path.exists():
            path = Path("/home/psh19/StockAutoTrader-V3/env.example")
        if not path.exists():
            pytest.skip(".env.example not found yet")
        return path.read_text()

    def test_has_app_key(self):
        content = self._read_example()
        assert "KIS_APP_KEY=" in content

    def test_has_app_secret(self):
        content = self._read_example()
        assert "KIS_APP_SECRET=" in content

    def test_has_account_no(self):
        content = self._read_example()
        assert "KIS_ACCOUNT_NO=" in content

    def test_has_live_trading_disabled(self):
        content = self._read_example()
        assert "LIVE_TRADING_ENABLED=false" in content

    def test_has_base_url(self):
        content = self._read_example()
        assert "KIS_BASE_URL=" in content

    def test_no_real_secrets(self):
        """실제 secret 값이 예제에 포함되지 않음"""
        content = self._read_example()
        # 빈 값 또는 설명만 있어야 함
        assert "PSH" not in content
        assert "44413716" not in content


class TestSmokeScript:
    """검증: smoke script 로직 (StubTransport 기반, 실제 호출 없음)"""

    def test_default_symbol(self):
        """기본 종목은 005930"""
        from scripts.kis_readonly_smoke import DEFAULT_SYMBOL
        assert DEFAULT_SYMBOL == "005930"

    def test_no_order_endpoints_referenced(self):
        """smoke script에 주문 endpoint 참조 없음"""
        import scripts.kis_readonly_smoke as smoke
        source = Path(smoke.__file__).read_text()
        order_keywords = ["order-cash", "order-credit", "order-rvsecncl",
                          "place_order", "submit_order", "buy_order", "sell_order"]
        for kw in order_keywords:
            assert kw not in source, f"Order keyword '{kw}' found in smoke script"

    def test_live_trading_disabled_checked(self):
        """LIVE_TRADING_ENABLED=false 확인 로직 포함"""
        import scripts.kis_readonly_smoke as smoke
        source = Path(smoke.__file__).read_text()
        assert "LIVE_TRADING_ENABLED" in source
        assert "false" in source.lower()

    def test_masked_output_only(self):
        """masked_dict 사용 확인"""
        import scripts.kis_readonly_smoke as smoke
        source = Path(smoke.__file__).read_text()
        assert "masked_dict" in source or "masked" in source.lower()

    def test_smoke_script_importable(self):
        """smoke script가 import 가능한 구조인지"""
        try:
            import scripts.kis_readonly_smoke as smoke
            assert hasattr(smoke, 'run_smoke_with_transport')
        except ImportError:
            pytest.skip("scripts package not yet created")


class TestSmokeWithStubTransport:
    """StubTransport 기반 smoke flow 검증"""

    def test_smoke_with_stub(self, monkeypatch):
        """StubTransport로 smoke 테스트 실행 (실제 호출 없음)"""
        monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
        from kis.transport import StubTransport
        from scripts.kis_readonly_smoke import run_smoke_with_transport

        transport = StubTransport(responses={
            "/oauth2/tokenP": {
                "access_token": "stub_token", "token_type": "Bearer",
                "expires_in": 86400,
            },
            "/uapi/domestic-stock/v1/quotations/chk-holiday": {
                "output": [{"bass_dt": "20260505"}]
            },
            "/uapi/domestic-stock/v1/quotations/market-status": {
                "output": {"market_status": "OPEN"}
            },
            "/uapi/price": {
                "output": {"stck_prpr": "75000"}
            },
        })

        result = run_smoke_with_transport(
            transport=transport,
            symbol="005930",
            app_key="test", app_secret="test",
            base_url="https://test.com",
        )
        assert "token" in result
        assert "holidays" in result
        assert "price" in result

    def test_smoke_no_secret_in_output(self, monkeypatch):
        """실행 결과에 secret 원문 없음"""
        monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
        from kis.transport import StubTransport
        from scripts.kis_readonly_smoke import run_smoke_with_transport

        transport = StubTransport(responses={
            "/oauth2/tokenP": {
                "access_token": "stub_token", "token_type": "Bearer",
                "expires_in": 86400,
            },
            "/uapi/domestic-stock/v1/quotations/chk-holiday": {
                "output": []
            },
            "/uapi/domestic-stock/v1/quotations/market-status": {
                "output": {"market_status": "OPEN"}
            },
            "/uapi/price": {
                "output": {"stck_prpr": "75000"}
            },
        })

        result = run_smoke_with_transport(
            transport=transport,
            symbol="005930",
            app_key="PSH_REAL_KEY_12345", app_secret="REAL_SECRET_ABCDEF",
            base_url="https://test.com",
        )
        output = str(result)
        assert "PSH_REAL_KEY_12345" not in output
        assert "REAL_SECRET_ABCDEF" not in output
