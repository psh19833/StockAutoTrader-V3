from __future__ import annotations

from audit_logging.correlation import correlation_id
from audit_logging.log_sanitizer import sanitize_value


def test_correlation_id_has_trade_prefix_and_not_empty():
    cid = correlation_id()
    assert cid.startswith("TRADE-")
    assert len(cid) > 12


def test_sanitize_value_masks_jwt_like_token():
    raw = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaa.bbbbbbbbbb"
    out = sanitize_value("message", raw)
    assert isinstance(out, str)
    assert "****" in out
    assert raw not in out


def test_sanitize_value_masks_telegram_token_pattern():
    raw = "1234567890:ABCdefGHIjklmNOPqrstUVWXyz_abc"
    out = sanitize_value("message", raw)
    assert isinstance(out, str)
    assert "****" in out
    assert raw not in out
