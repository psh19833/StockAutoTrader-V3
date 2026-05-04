"""Phase 1 — TDD: Secret Masking 테스트"""
import pytest
from kis.raw_logger import (
    mask_account_no,
    mask_app_key,
    mask_app_secret,
    mask_token,
    mask_telegram_bot_token,
    mask_telegram_chat_id,
    sanitize_headers,
    KisSafeLogger,
)

_SAMPLE_ACCOUNT = "4441371601"
_SAMPLE_APP_KEY = "PSHabcdef1234567890abcd"
_SAMPLE_SECRET = "qwertyuiop1234567890abcdefghijklmnop"
_SAMPLE_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
_SAMPLE_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
_SAMPLE_CHAT_ID = "2118976841"


class TestMaskAccountNo:
    def test_mask_full_account(self):
        result = mask_account_no(_SAMPLE_ACCOUNT)
        assert result == "4441****01"
        assert _SAMPLE_ACCOUNT not in result

    def test_mask_short_account(self):
        """짧은 계좌번호도 마스킹"""
        result = mask_account_no("12345")
        assert result != "12345"
        assert len(result) == len("12345")

    def test_empty_string(self):
        assert mask_account_no("") == ""


class TestMaskAppKey:
    def test_mask_app_key(self):
        result = mask_app_key(_SAMPLE_APP_KEY)
        assert "PSH" not in result or "abcdef" not in result
        assert len(result) > 0
        assert result != _SAMPLE_APP_KEY
        assert result.startswith("PSH")

    def test_empty_string(self):
        assert mask_app_key("") == ""


class TestMaskAppSecret:
    def test_mask_secret(self):
        result = mask_app_secret(_SAMPLE_SECRET)
        assert len(result) > 0
        assert result != _SAMPLE_SECRET
        # 첫 4자 + **** + 마지막 4자 패턴
        assert result.startswith("qwer")
        assert result.endswith("mnop")

    def test_empty_string(self):
        assert mask_app_secret("") == ""


class TestMaskToken:
    def test_mask_token(self):
        result = mask_token(_SAMPLE_TOKEN)
        assert result != _SAMPLE_TOKEN
        assert result.startswith("eyJ")
        # 마스킹 영역(4자리 ****)이 포함되어야 함
        assert "****" in result
        # 결과는 앞3+****+뒤4 패턴으로, 원본과 같을 수 없음
        assert result == "eyJ****wIn0"

    def test_empty_string(self):
        assert mask_token("") == ""


class TestMaskTelegramBotToken:
    def test_mask_bot_token(self):
        result = mask_telegram_bot_token(_SAMPLE_BOT_TOKEN)
        assert result != _SAMPLE_BOT_TOKEN
        # 토큰 내 ':' 문자는 패턴 유지를 위해 보존
        assert ":" in result
        assert result.startswith("1234")
        assert result.endswith("wxyz")

    def test_empty_string(self):
        assert mask_telegram_bot_token("") == ""


class TestMaskTelegramChatId:
    def test_mask_chat_id(self):
        result = mask_telegram_chat_id(_SAMPLE_CHAT_ID)
        assert result != _SAMPLE_CHAT_ID
        assert result == "2118****841"

    def test_empty_string(self):
        assert mask_telegram_chat_id("") == ""


class TestSanitizeHeaders:
    def test_masks_authorization(self):
        headers = {"authorization": f"Bearer {_SAMPLE_TOKEN}"}
        result = sanitize_headers(headers)
        assert _SAMPLE_TOKEN not in str(result)
        assert "Bearer" in str(result.get("authorization", ""))

    def test_masks_appkey(self):
        headers = {"appkey": _SAMPLE_APP_KEY}
        result = sanitize_headers(headers)
        assert _SAMPLE_APP_KEY not in str(result)

    def test_masks_appsecret(self):
        headers = {"appsecret": _SAMPLE_SECRET}
        result = sanitize_headers(headers)
        assert _SAMPLE_SECRET not in str(result)

    def test_leaves_normal_headers(self):
        headers = {"content-type": "application/json"}
        result = sanitize_headers(headers)
        assert result["content-type"] == "application/json"

    def test_case_insensitive_matching(self):
        headers = {"APPKEY": _SAMPLE_APP_KEY, "Authorization": f"Bearer {_SAMPLE_TOKEN}"}
        result = sanitize_headers(headers)
        assert _SAMPLE_APP_KEY not in str(result)
        assert _SAMPLE_TOKEN not in str(result)


class TestKisSafeLogger:
    def test_info_sanitizes_message(self):
        """KisSafeLogger의 info 호출 시 secret 마스킹"""
        logger = KisSafeLogger("test_logger")
        msg = logger.sanitize(f"account={_SAMPLE_ACCOUNT}, token={_SAMPLE_TOKEN}")
        assert _SAMPLE_ACCOUNT not in msg
        assert _SAMPLE_TOKEN not in msg
        assert "account=4441****01" in msg

    def test_debug_sanitizes(self):
        logger = KisSafeLogger("test_logger")
        msg = logger.sanitize(f"appkey={_SAMPLE_APP_KEY}")
        assert _SAMPLE_APP_KEY not in msg

    def test_safe_log_keeps_normal_text(self):
        logger = KisSafeLogger("test_logger")
        msg = logger.sanitize("Normal log message without secrets")
        assert msg == "Normal log message without secrets"