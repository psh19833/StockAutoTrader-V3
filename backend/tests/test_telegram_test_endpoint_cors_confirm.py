from __future__ import annotations

from main import telegram_test


async def _call(payload: dict):
    return await telegram_test(payload)


def test_telegram_test_endpoint_without_confirm_is_dry_run_and_no_secrets():
    import asyncio
    res = asyncio.run(_call({}))
    assert res["sent"] is False
    assert res.get("mode") == "dry-run"
    joined = str(res).lower()
    for k in ["appkey", "appsecret", "access_token", "approval_key", "telegram_bot_token"]:
        assert k not in joined
