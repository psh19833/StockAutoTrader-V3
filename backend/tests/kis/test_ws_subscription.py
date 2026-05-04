"""Tests for backend/kis/ws_subscription.py — WebSocket subscribe/unsubscribe payloads."""
import json
import pytest

from kis.ws_subscription import (
    SubscribeRequest,
    build_subscribe_payload,
    build_unsubscribe_payload,
    MASKED_APPROVAL_KEY,
)


# ── SubscribeRequest ─────────────────────────────────────────────────────────

class TestSubscribeRequest:
    def test_create(self):
        req = SubscribeRequest(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc123",
        )
        assert req.tr_id == "H0STCNT0"
        assert req.symbol == "005930"
        assert req.approval_key == "real-key-abc123"

    def test_approval_key_masked_in_repr(self):
        req = SubscribeRequest(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc123",
        )
        r = repr(req)
        assert "real-key-abc123" not in r
        assert MASKED_APPROVAL_KEY in r

    def test_approval_key_masked_in_str(self):
        req = SubscribeRequest(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc123",
        )
        s = str(req)
        assert "real-key-abc123" not in s

    def test_get_masked_approval_key(self):
        req = SubscribeRequest(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc123",
        )
        assert req.get_masked_approval_key() == MASKED_APPROVAL_KEY

    def test_get_approval_key_returns_real(self):
        req = SubscribeRequest(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc123",
        )
        assert req.get_approval_key() == "real-key-abc123"


# ── build_subscribe_payload ──────────────────────────────────────────────────

class TestBuildSubscribePayload:
    def test_trade_tick_payload(self):
        payload = build_subscribe_payload(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key",
        )
        assert "header" in payload
        assert "body" in payload
        assert payload["header"]["approval_key"] == "real-key"
        assert payload["header"]["tr_type"] == "1"  # register
        assert payload["body"]["input"]["tr_id"] == "H0STCNT0"
        assert "005930" in str(payload["body"]["input"])

    def test_order_book_payload(self):
        payload = build_subscribe_payload(
            tr_id="H0STASP0",
            symbol="005930",
            approval_key="real-key",
        )
        assert payload["body"]["input"]["tr_id"] == "H0STASP0"

    def test_payload_serializable(self):
        payload = build_subscribe_payload(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key",
        )
        dumped = json.dumps(payload)
        assert "H0STCNT0" in dumped
        assert "005930" in dumped

    def test_approval_key_in_payload_for_wire(self):
        """approval_key is included in the wire-level payload."""
        payload = build_subscribe_payload(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc",
        )
        assert payload["header"]["approval_key"] == "real-key-abc"

    def test_payload_can_be_masked_for_logging(self):
        """The payload can be masked for logging (smoke script handles this)."""
        payload = build_subscribe_payload(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key-abc",
        )
        # Simulate what smoke script does: mask approval_key for display
        display = dict(payload)
        display["header"] = dict(display["header"])
        display["header"]["approval_key"] = MASKED_APPROVAL_KEY
        dumped = json.dumps(display)
        assert "real-key-abc" not in dumped
        assert MASKED_APPROVAL_KEY in dumped


# ── build_unsubscribe_payload ────────────────────────────────────────────────

class TestBuildUnsubscribePayload:
    def test_unsubscribe_payload(self):
        payload = build_unsubscribe_payload(
            tr_id="H0STCNT0",
            symbol="005930",
            approval_key="real-key",
        )
        assert payload["header"]["tr_type"] == "2"  # unregister
        assert payload["body"]["input"]["tr_id"] == "H0STCNT0"

    def test_unsubscribe_different_tr_id(self):
        payload = build_unsubscribe_payload(
            tr_id="H0STASP0",
            symbol="005930",
            approval_key="real-key",
        )
        assert payload["body"]["input"]["tr_id"] == "H0STASP0"


# ── Masked constant ──────────────────────────────────────────────────────────

class TestMaskedConstant:
    def test_masked_approval_key_value(self):
        assert MASKED_APPROVAL_KEY == "****-****-****"

    def test_masked_is_not_real(self):
        assert "real" not in MASKED_APPROVAL_KEY
        assert len(MASKED_APPROVAL_KEY) < 20
