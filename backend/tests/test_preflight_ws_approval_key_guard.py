from __future__ import annotations

import pytest

from kis.ws_client import GuardedRealWebSocketClient


def test_ws_client_connect_requires_approval_key_before_network():
    client = GuardedRealWebSocketClient()
    # If the implementation checks approval_key first, it should raise ValueError
    # before any attempt to reach the base_url.
    with pytest.raises(ValueError):
        client.connect(approval_key="", base_url="ws://dummy")
