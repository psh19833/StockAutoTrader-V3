"""KIS Query Facade — 조회 전용 통합 서비스

market_schedule_api, market_data_api, stock_info_api, account_api를
하나의 facade로 통합. 주문 기능 없음.
"""
from __future__ import annotations
from kis.client import KisClient
from kis.transport import StubTransport


class KisQueryFacade:
    """KIS 조회 전용 Facade — 주문 API 절대 미포함"""

    def __init__(self, client: KisClient | None = None,
                 transport = None, base_url: str = ""):
        self._client = client or KisClient(
            base_url=base_url or "https://openapi.koreainvestment.com:9443",
            transport=transport,
        )

    def _safe_call(self, fn, *args, **kwargs) -> dict:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # Keep visibility without leaking exception messages (may contain secrets).
            return {
                "data_available": False,
                "source": "KIS_API",
                "source_endpoints": (),
                "error_type": type(e).__name__,
                "reason_code": "KIS_QUERY_FAILED",
                "reason_text": "KIS query failed",
            }

    # ── Market Schedule ──

    def get_holidays(self) -> list[str]:
        try:
            from kis.market_schedule_api import MarketScheduleApi
            api = MarketScheduleApi(client=self._client)
            return api.get_holidays()
        except Exception:
            return []

    def get_market_status(self) -> dict:
        return self._safe_call(lambda: self._call_market_status())

    def _call_market_status(self) -> dict:
        from kis.market_schedule_api import MarketScheduleApi
        api = MarketScheduleApi(client=self._client)
        return api.get_market_status()

    # ── Market Data ──

    def get_current_price(self, symbol: str) -> dict:
        return self._safe_call(lambda: self._call_price(symbol))

    def _call_price(self, symbol: str) -> dict:
        from kis.market_data_api import MarketDataApi
        api = MarketDataApi(client=self._client)
        return api.get_current_price(symbol)

    def get_orderbook(self, symbol: str) -> dict:
        return self._safe_call(lambda: self._call_orderbook(symbol))

    def _call_orderbook(self, symbol: str) -> dict:
        from kis.market_data_api import MarketDataApi
        api = MarketDataApi(client=self._client)
        return api.get_orderbook(symbol)

    def get_execution_strength(self, symbol: str) -> dict:
        return self._safe_call(lambda: self._call_execution(symbol))

    def _call_execution(self, symbol: str) -> dict:
        from kis.market_data_api import MarketDataApi
        api = MarketDataApi(client=self._client)
        return api.get_execution_strength(symbol)

    # ── Stock Info ──

    def get_stock_info(self, symbol: str) -> dict:
        return self._safe_call(lambda: self._call_stock_info(symbol))

    def _call_stock_info(self, symbol: str) -> dict:
        from kis.stock_info_api import StockInfoApi
        api = StockInfoApi(client=self._client)
        return api.get_stock_info(symbol)

    # ── Account ──

    def get_balance(self) -> dict:
        return self._safe_call(lambda: self._call_balance())

    def _call_balance(self) -> dict:
        from kis.account_api import AccountApi
        api = AccountApi(client=self._client)
        return api.get_balance()

    def get_fills(self) -> list[dict]:
        try:
            from kis.account_api import AccountApi
            api = AccountApi(client=self._client)
            return api.get_fills()
        except Exception:
            return []
