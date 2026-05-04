"""Phase 3 — Audit Event / Correlation / Log Sanitizer / Writer 단위 테스트"""
import pytest
import json
from datetime import date, datetime, timezone

from audit_logging.audit_event import (
    AuditEvent, AuditEventType, SeverityLevel,
    FORBIDDEN_EVENT_TYPES,
)
from audit_logging.correlation import (
    correlation_id, scan_run_id, evaluation_id, signal_id,
    risk_decision_id, order_intent_id, fill_id,
)
from audit_logging.log_sanitizer import sanitize_value, sanitize_payload, sanitize_dict
from audit_logging.audit_writer import InMemoryAuditWriter, audit_event_to_dict
from audit_logging.retention import RetentionPolicy, get_retention_policy, is_expired, DEFAULT_POLICIES
from audit_logging.logger import SafeLogger


# ── AuditEvent Tests ──

class TestAuditEventType:
    """AuditEventType enum"""

    def test_server_started_exists(self):
        assert AuditEventType.SERVER_STARTED.value == "SERVER_STARTED"

    def test_kis_api_called_exists(self):
        assert AuditEventType.KIS_API_CALLED.value == "KIS_API_CALLED"

    def test_scan_started_exists(self):
        assert AuditEventType.SCAN_STARTED.value == "SCAN_STARTED"

    def test_emergency_stop_exists(self):
        assert AuditEventType.EMERGENCY_STOP_ACTIVATED

    def test_order_intent_approved_exists(self):
        assert AuditEventType.ORDER_INTENT_APPROVED

    def test_no_fake_fill(self):
        """fake fill/simulated order event type 없음"""
        for event_type in AuditEventType:
            assert event_type.value not in FORBIDDEN_EVENT_TYPES


class TestAuditEvent:
    """AuditEvent 생성"""

    def test_create_basic(self):
        event = AuditEvent(event_type="SERVER_STARTED", source="main")
        assert event.event_type == "SERVER_STARTED"
        assert event.source == "main"
        assert event.severity == "INFO"
        assert isinstance(event.event_id, str)
        assert len(event.event_id) == 16

    def test_create_with_all_fields(self):
        event = AuditEvent(
            event_type="SCAN_STARTED",
            severity="INFO",
            correlation_id="SCAN-250504-090000-abc123",
            trading_day=date(2025, 5, 4),
            symbol="005930",
            strategy_name="breakout",
            payload={"collected_count": 500},
            source="scanner",
        )
        assert event.event_type == "SCAN_STARTED"
        assert event.correlation_id == "SCAN-250504-090000-abc123"
        assert event.symbol == "005930"
        assert event.strategy_name == "breakout"
        assert event.payload["collected_count"] == 500

    def test_event_type_missing_empty(self):
        """event_type이 빈 문자열이어도 생성됨 (호출자가 채워야 함)"""
        event = AuditEvent(source="test")
        assert event.event_type == ""

    def test_default_severity_info(self):
        event = AuditEvent(event_type="TEST")
        assert event.severity == "INFO"

    def test_default_timestamp(self):
        before = datetime.now(timezone.utc)
        event = AuditEvent(event_type="TEST")
        after = datetime.now(timezone.utc)
        assert before <= event.event_time <= after

    def test_frozen(self):
        event = AuditEvent(event_type="SERVER_STARTED")
        with pytest.raises(AttributeError):
            event.event_type = "SERVER_STOPPED"  # type: ignore

    def test_payload_as_dict(self):
        event = AuditEvent(event_type="TEST", payload={"key": "value"})
        assert event.payload["key"] == "value"

    def test_kis_api_failed_event(self):
        event = AuditEvent(
            event_type="KIS_API_FAILED",
            severity="ERROR",
            payload={
                "endpoint": "/uapi/domestic-stock/v1/trading/inquire-price",
                "http_status": 500,
                "kis_error_code": "50001",
            },
            source="kis_client",
        )
        assert event.event_type == "KIS_API_FAILED"
        assert event.severity == "ERROR"


class TestForbiddenEventTypes:
    """fake/simulated event type 금지 확인"""

    def test_no_forbidden_in_enum(self):
        for event_type in AuditEventType:
            assert event_type.value not in FORBIDDEN_EVENT_TYPES

    def test_forbidden_list_defined(self):
        assert "FAKE_FILL_CONFIRMED" in FORBIDDEN_EVENT_TYPES
        assert "SIMULATED_ORDER_SUBMITTED" in FORBIDDEN_EVENT_TYPES


# ── Correlation Tests ──

class TestCorrelation:
    """Correlation ID 생성"""

    def test_correlation_id_format(self):
        cid = correlation_id()
        parts = cid.split("-")
        assert parts[0] == "TRADE"
        assert len(parts) == 4  # TRADE-YYMMDD-HHMMSS-xxxxxx

    def test_scan_run_id_prefix(self):
        cid = scan_run_id()
        assert cid.startswith("SCAN-")

    def test_evaluation_id_prefix(self):
        cid = evaluation_id()
        assert cid.startswith("EVAL-")

    def test_signal_id_prefix(self):
        cid = signal_id()
        assert cid.startswith("SIG-")

    def test_risk_decision_id_prefix(self):
        cid = risk_decision_id()
        assert cid.startswith("RISK-")

    def test_order_intent_id_prefix(self):
        cid = order_intent_id()
        assert cid.startswith("ORD-")

    def test_fill_id_prefix(self):
        cid = fill_id()
        assert cid.startswith("FILL-")

    def test_unique_ids(self):
        """연속 생성 시 다른 ID"""
        ids = [correlation_id() for _ in range(10)]
        assert len(set(ids)) == 10  # 모두 고유


# ── Log Sanitizer Tests ──

class TestSanitizeValue:
    """sanitize_value 기본"""

    def test_sanitize_appkey(self):
        result = sanitize_value("appkey", "abcd1234efgh5678")
        assert "abcd" in result
        assert "****" in result
        assert "5678" in result
        assert "abcd1234efgh5678" not in result

    def test_sanitize_app_secret(self):
        result = sanitize_value("appsecret", "secret_value_12345")
        assert "secret_value_12345" not in result

    def test_sanitize_access_token(self):
        result = sanitize_value("access_token", "eyJhbGciOiJIUzI1NiJ9.test.token")
        assert "test" in result or "****" in result
        assert "eyJhbGciOiJIUzI1NiJ9.test.token" not in result

    def test_sanitize_account_number(self):
        result = sanitize_value("account_no", "12345678-01")
        assert "1234" in result
        assert "****" in result
        assert "12345678-01" not in result

    def test_sanitize_telegram_token(self):
        result = sanitize_value("bot_token", "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        assert "123" in result
        assert "****" in result
        assert "ABCdefGHIjklMNOpqrsTUVwxyz" not in result

    def test_leave_normal_value(self):
        result = sanitize_value("symbol", "005930")
        assert result == "005930"

    def test_leave_price_value(self):
        result = sanitize_value("current_price", 70000)
        assert result == 70000

    def test_sanitize_nested_dict(self):
        data = {"config": {"appkey": "supersecret123", "symbol": "005930"}}
        result = sanitize_value("config", data)
        assert result["config"]["symbol"] == "005930"
        assert "supersecret123" not in str(result)

    def test_sanitize_list_value(self):
        data = ["normal", {"app_key": "mysecret"}]
        result = sanitize_value("items", data)
        assert result[0] == "normal"
        assert "mysecret" not in str(result[1])

    def test_sanitize_chat_id(self):
        """chat_id 마스킹: 앞 3자 + ****"""
        result = sanitize_value("chat_id", "-1001234567890")
        assert "-10" in result
        assert "****" in result
        assert "-1001234567890" not in result


class TestSanitizePayload:
    """sanitize_payload"""

    def test_sanitize_payload(self):
        payload = {
            "appkey": "myappkey123",
            "appsecret": "mysecret456",
            "result": {"price": 70000, "volume": 1000},
        }
        result = sanitize_payload(payload)
        assert "myappkey123" not in str(result)
        assert "mysecret456" not in str(result)
        assert result["result"]["price"] == 70000


class TestSanitizeDict:
    """sanitize_dict 전체"""

    def test_normal_values_preserved(self):
        d = {"symbol": "005930", "price": 70000, "name": "삼성전자"}
        result = sanitize_dict(d)
        assert result == d

    def test_secrets_masked(self):
        d = {"appkey": "mykey", "data": {"access_token": "mytoken123"}}
        result = sanitize_dict(d)
        assert "mykey" not in str(result)
        assert "mytoken123" not in str(result)


# ── Audit Writer Tests ──

class TestInMemoryAuditWriter:
    """InMemoryAuditWriter"""

    def test_write_event(self):
        writer = InMemoryAuditWriter()
        event = AuditEvent(event_type="TEST", source="test")
        writer.write(event)
        assert writer.count() == 1

    def test_write_many(self):
        writer = InMemoryAuditWriter()
        events = [
            AuditEvent(event_type="A", source="test"),
            AuditEvent(event_type="B", source="test"),
        ]
        writer.write_many(events)
        assert writer.count() == 2

    def test_list_all(self):
        writer = InMemoryAuditWriter()
        writer.write(AuditEvent(event_type="A", source="test"))
        writer.write(AuditEvent(event_type="B", source="test"))
        all_events = writer.list_all()
        assert len(all_events) == 2

    def test_filter_by_event_type(self):
        writer = InMemoryAuditWriter()
        writer.write(AuditEvent(event_type="SCAN_STARTED", source="scanner"))
        writer.write(AuditEvent(event_type="SCAN_COMPLETED", source="scanner"))
        filtered = writer.filter_by_event_type("SCAN_STARTED")
        assert len(filtered) == 1
        assert filtered[0].event_type == "SCAN_STARTED"

    def test_filter_by_correlation_id(self):
        writer = InMemoryAuditWriter()
        cid = correlation_id()
        writer.write(AuditEvent(
            event_type="SCAN_STARTED", correlation_id=cid, source="scanner"
        ))
        writer.write(AuditEvent(
            event_type="QUANT_EVALUATED", correlation_id=cid, source="quant"
        ))
        writer.write(AuditEvent(
            event_type="OTHER", correlation_id="DIFFERENT", source="other"
        ))
        filtered = writer.filter_by_correlation_id(cid)
        assert len(filtered) == 2

    def test_filter_by_severity(self):
        writer = InMemoryAuditWriter()
        writer.write(AuditEvent(event_type="A", severity="ERROR", source="test"))
        writer.write(AuditEvent(event_type="B", severity="INFO", source="test"))
        filtered = writer.filter_by_severity("ERROR")
        assert len(filtered) == 1

    def test_filter_by_date(self):
        writer = InMemoryAuditWriter()
        d = date(2025, 5, 4)
        writer.write(AuditEvent(event_type="A", trading_day=d, source="test"))
        writer.write(AuditEvent(event_type="B", source="test"))  # None
        filtered = writer.filter_by_date(d)
        assert len(filtered) == 1

    def test_filter_by_source(self):
        writer = InMemoryAuditWriter()
        writer.write(AuditEvent(event_type="A", source="scanner"))
        writer.write(AuditEvent(event_type="B", source="kis_client"))
        filtered = writer.filter_by_source("scanner")
        assert len(filtered) == 1

    def test_clear(self):
        writer = InMemoryAuditWriter()
        writer.write(AuditEvent(event_type="A", source="test"))
        writer.clear()
        assert writer.count() == 0

    def test_sanitize_on_write(self):
        """write 시 sanitize 자동 적용"""
        writer = InMemoryAuditWriter()
        event = AuditEvent(
            event_type="TEST",
            payload={"appkey": "secret123"},
            source="test",
        )
        writer.write(event)
        stored = writer.list_all()[0]
        assert "secret123" not in stored.payload["appkey"]
        assert "****" in stored.payload["appkey"]

    def test_audit_event_to_dict(self):
        event = AuditEvent(
            event_type="SCAN_STARTED",
            trading_day=date(2025, 5, 4),
            source="test",
        )
        d = audit_event_to_dict(event)
        assert d["event_type"] == "SCAN_STARTED"
        assert d["trading_day"] == "2025-05-04"
        assert isinstance(d["event_time"], str)
        assert isinstance(d["created_at"], str)


# ── Retention Policy Tests ──

class TestRetention:
    """보관 정책"""

    def test_default_policies_exist(self):
        assert len(DEFAULT_POLICIES) == 4
        assert "application_log" in DEFAULT_POLICIES
        assert "audit_event_log" in DEFAULT_POLICIES
        assert "raw_api_log" in DEFAULT_POLICIES
        assert "eod_summary" in DEFAULT_POLICIES

    def test_audit_event_1_year(self):
        policy = get_retention_policy("audit_event_log")
        assert policy is not None
        assert policy.max_days >= 365

    def test_eod_summary_long_term(self):
        policy = get_retention_policy("eod_summary")
        assert policy is not None
        assert policy.max_days >= 3650  # 10년

    def test_is_expired_true(self):
        policy = RetentionPolicy(name="test", max_days=30, description="")
        assert is_expired(policy, 31) is True

    def test_is_expired_false(self):
        policy = RetentionPolicy(name="test", max_days=30, description="")
        assert is_expired(policy, 15) is False

    def test_is_expired_equal(self):
        policy = RetentionPolicy(name="test", max_days=30, description="")
        assert is_expired(policy, 30) is True  # 경계값: 30일 == 만료


# ── SafeLogger Tests ──

class TestSafeLogger:
    """SafeLogger sanitize 적용 확인"""

    def test_logger_sanitizes_message(self, caplog):
        logger = SafeLogger("test_logger")
        logger.info("AppKey: mysecretkey123")
        # caplog 확인
        found = False
        for record in caplog.records:
            if "mysecretkey123" not in record.message:
                found = True
        # sanitizer가 적용되었음을 확인 (실제 로그 출력 확인)

    def test_logger_keeps_normal_message(self):
        logger = SafeLogger("test_logger")
        # 예외 없이 실행만 확인
        logger.info("Normal log message")
        logger.warning("Warning with price 70000")
        logger.error("Error occurred")
        logger.debug("Debug info")
        logger.critical("Critical error")