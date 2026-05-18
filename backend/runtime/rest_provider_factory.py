"""Factory helpers for optional read-only REST providers.

Keep preview/diagnostic scripts clean and avoid importing heavy components
unless needed.

Rules:
- No order endpoints.
- No .env modification.
"""

from __future__ import annotations

from typing import Any

from runtime.rest_market_data_provider import RestMarketDataProvider


def maybe_create_kis_rest_provider() -> tuple[RestMarketDataProvider | None, dict[str, Any]]:
    """Create a GET-only KIS REST provider if env credentials exist.

    Returns:
      (provider_or_none, meta)
    meta always safe to log (no secrets).
    """
    try:
        from kis.credentials import KisCredentials

        creds = KisCredentials.from_env()
        if not getattr(creds, "app_key", "") or not getattr(creds, "app_secret", ""):
            return None, {"configured": False, "reason": "missing_env_credentials"}

        # Build token + client (read-only).
        from kis.transport import RealTransport
        from kis.token_provider import KisTokenProvider
        from kis.client import KisClient
        from kis.query_facade import KisQueryFacade
        from runtime.kis_rest_market_data_provider import KisRestMarketDataProvider

        transport = RealTransport(base_url=creds.base_url, timeout=15)
        provider = KisTokenProvider(
            app_key=creds.app_key,
            app_secret=creds.app_secret,
            base_url=creds.base_url,
            transport=transport,
        )
        token = provider.issue_token()

        client = KisClient(
            base_url=creds.base_url,
            transport=transport,
            app_key=creds.app_key,
            app_secret=creds.app_secret,
        )
        client.auth_manager.set_token(token)

        facade = KisQueryFacade(client=client)
        return KisRestMarketDataProvider(facade), {
            "configured": True,
            "provider_type": "KisRestMarketDataProvider",
            "base_url": creds.base_url,
        }
    except Exception as e:
        return None, {"configured": False, "reason": f"create_failed:{type(e).__name__}"}
