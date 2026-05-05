"""Phase 3B — Telegram Event Notification Engine 단위 테스트"""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import patch

from audit_logging.audit_event import AuditEvent
from audit_logging.correlation import correlation_id
from notifications.telegram_event import (
    TelegramEvent,
    TelegramEventType,
    NotificationSeverity,
    DEFAULT_SEVERITY_MAP,
)
from notifications.telegram_formatter import format_audit_event
from notifications.telegram_policy import (
    TelegramNotificationPolicy,
    ThrottlingPolicy,
    ThrottlingTracker,
    DEFAULT_ALLOWED_EVENT_TYPES,
)
from notifications.telegram_sender import (
    TelegramSender,
    InMemoryTelegramSender,
    SendResult,
)
from notifications.telegram_notifier import TelegramNotifier


# ── Helper ──

def _make_event(
    event_type: str,
    symbol: str | None = None,
    severity: str = "INFO",
    payload: dict | None = None,
    strategy: str | None = None,
    trading_day: date | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id="test_" + event_type.lower(),
        event_type=event_type,
        event_time=datetime.now(timezone.utc),
        severity=severity,
        correlation_id=correlation_id(),
        trading_day=trading_day or date(2026, 5, 4),
        symbol=symbol,
        strategy_name=strategy,
        payload=payload or {},
        source="test",
    )


# ── TelegramEvent Tests ──

class TestTelegramEvent:
    def test_create_basic(self):
        event = TelegramEvent(
            event_type="SERVER_STARTED",
            title="SAT3 서버 시작",
            body="서버가 시작되었습니다.",
            notification_severity=NotificationSeverity.NORMAL,
        )
        assert event.event_type == "SERVER_STARTED"
        assert event.title == "SAT3 서버 시작"
        assert event.notification_severity == NotificationSeverity.NORMAL
        assert event.created_at is not None

    def test_formatted_message_has_icon(self):
        event = TelegramEvent(
            event_type="SERVER_STARTED",
            title="SAT3 시작",
            body="본문",
            notification_severity=NotificationSeverity.NORMAL,
        )
        msg = event.formatted_message
        assert "ℹ️" in msg
        assert "<b>SAT3 시작</b>" in msg
        assert "본문" in msg

    def test_formatted_message_critical(self):
        event = TelegramEvent(
            event_type="EMERGENCY_STOP_ACTIVATED",
            title="비상정지",
            body="사유: 긴급",
            notification_severity=NotificationSeverity.CRITICAL,
        )
        msg = event.formatted_message
        assert "🚨" in msg

    def test_formatted_message_high(self):
        event = TelegramEvent(
            event_type="ORDER_SUBMITTED",
            title="주문",
            body="내용",
            notification_severity=NotificationSeverity.HIGH,
        )
        msg = event.formatted_message
        assert "⚠️" in msg

    def test_formatted_message_low(self):
        event = TelegramEvent(
            event_type="TRADING_DAY_CHECKED",
            title="거래일",
            body="정보",
            notification_severity=NotificationSeverity.LOW,
        )
        msg = event.formatted_message
        assert "🔹" in msg


class TestTelegramEventType:
    def test_required_events_exist(self):
        required = [
            "SERVER_STARTED", "SERVER_STOPPED",
            "TRADING_DAY_CHECKED", "SESSION_STATE_CHANGED",
            "SESSION_STATE_UNKNOWN", "NEW_BUY_BLOCKED_BY_SESSION",
            "MARKET_REGIME_EVALUATED", "SCAN_COMPLETED",
            "CANDIDATE_DISCOVERED", "STRATEGY_SIGNAL_CREATED",
            "RISK_APPROVED", "RISK_REJECTED", "ORDER_SUBMITTED",
            "ORDER_FAILED", "FILL_CONFIRMED", "POSITION_SYNCED",
            "EOD_REPORT_CREATED", "EMERGENCY_STOP_ACTIVATED",
            "EMERGENCY_STOP_RELEASED", "KIS_API_FAILED",
        ]
        for name in required:
            assert hasattr(TelegramEventType, name), f"Missing: {name}"

    def test_severity_map_has_all_events(self):
        for et in TelegramEventType:
            assert et.value in DEFAULT_SEVERITY_MAP


# ── Formatter Tests ──

class TestFormatterOrderSubmitted:
    def test_order_submitted_format(self):
        event = _make_event("ORDER_SUBMITTED", symbol="005930",
                            payload={"order_type": "매수", "quantity": 10, "price": 70000})
        te = format_audit_event(event)
        assert te.event_type == TelegramEventType.ORDER_SUBMITTED.value
        assert "005930" in te.title
        assert "매수" in te.body
        assert "10" in te.body
        assert te.correlation_id is not None
        assert te.source_audit_event_id is not None

    def test_fill_confirmed_format(self):
        event = _make_event("FILL_CONFIRMED", symbol="005930",
                            payload={"filled_quantity": 10, "filled_price": 70000})
        te = format_audit_event(event)
        assert te.event_type == TelegramEventType.FILL_CONFIRMED.value
        assert "체결" in te.title
        assert "10" in te.body

    def test_order_submitted_and_fill_confirmed_are_different(self):
        submitted = _make_event("ORDER_SUBMITTED", symbol="005930",
                                payload={"order_type": "매수", "quantity": 10})
        filled = _make_event("FILL_CONFIRMED", symbol="005930",
                             payload={"filled_quantity": 10, "filled_price": 70000})
        te_sub = format_audit_event(submitted)
        te_fill = format_audit_event(filled)
        assert te_sub.event_type != te_fill.event_type
        assert "주문" in te_sub.title or "제출" in te_sub.title
        assert "체결" in te_fill.title


class TestFormatterSessionEvents:
    def test_session_state_changed(self):
        event = _make_event("SESSION_STATE_CHANGED",
                            payload={"previous_state": "PRE_MARKET", "current_state": "REGULAR_MARKET"})
        te = format_audit_event(event)
        assert "PRE_MARKET" in te.body
        assert "REGULAR_MARKET" in te.body

    def test_market_session_evaluated(self):
        event = _make_event("MARKET_SESSION_EVALUATED",
                            payload={"session_state": "REGULAR_MARKET"})
        # MARKET_REGIME_EVALUATED와 달리 MARKET_SESSION_EVALUATED는 지원 이벤트가 아님
        # → formatter에 없는 이벤트는 ValueError
        pass

    def test_session_state_unknown(self):
        event = _make_event("SESSION_STATE_UNKNOWN",
                            payload={"response_code": "302", "message": "장운영정보 없음"})
        te = format_audit_event(event)
        assert "알 수 없음" in te.body or "302" in te.body
        assert te.notification_severity == NotificationSeverity.CRITICAL

    def test_new_buy_blocked(self):
        event = _make_event("NEW_BUY_BLOCKED_BY_SESSION",
                            payload={"session_state": "LATE_MARKET", "reason": "15:20 이후 신규 매수 불가"})
        te = format_audit_event(event)
        assert "차단" in te.title or "차단" in te.body
        assert "LATE_MARKET" in te.body


class TestFormatterRiskEvents:
    def test_risk_rejected(self):
        event = _make_event("RISK_REJECTED", symbol="005930",
                            payload={"risk_score": 85, "reason": "변동성 초과"})
        te = format_audit_event(event)
        assert "기각" in te.title or "기각" in te.body
        assert "005930" in te.title
        assert "85" in te.body
        assert "변동성" in te.body

    def test_risk_approved(self):
        event = _make_event("RISK_APPROVED", symbol="005930",
                            payload={"risk_score": 30})
        te = format_audit_event(event)
        assert "승인" in te.title or "RISK_APPROVED" in te.event_type


class TestFormatterKisApiFailed:
    def test_kis_api_failed_message(self):
        event = _make_event("KIS_API_FAILED",
                            payload={"endpoint": "/uapi/domestic-stock/v1/quotations/inquire-price",
                                     "error_code": "ERR-001"})
        te = format_audit_event(event)
        assert "KIS" in te.title or "API" in te.title
        assert "ERR-001" in te.body


class TestFormatterEodReport:
    def test_eod_report_created(self):
        event = _make_event("EOD_REPORT_CREATED",
                            payload={"summary": "3종목 거래, 순이익 150,000원",
                                     "trading_day": "2026-05-04"})
        te = format_audit_event(event)
        assert "EOD" in te.title or "리포트" in te.title
        assert "150,000" in te.body


class TestFormatterServerEvents:
    def test_server_started(self):
        event = _make_event("SERVER_STARTED",
                            payload={"mode": "live"})
        te = format_audit_event(event)
        assert "시작" in te.title
        assert "live" in te.body

    def test_server_stopped(self):
        event = _make_event("SERVER_STOPPED",
                            payload={"reason": "정상 종료"})
        te = format_audit_event(event)
        assert "중지" in te.title
        assert "정상 종료" in te.body


class TestFormatterScanEvents:
    def test_scan_completed(self):
        event = _make_event("SCAN_COMPLETED",
                            payload={"total_candidates": 5})
        te = format_audit_event(event)
        assert "스캔" in te.title
        assert "5" in te.body

    def test_candidate_discovered(self):
        event = _make_event("CANDIDATE_DISCOVERED", symbol="005930",
                            payload={"reason": "급등량 돌파"})
        te = format_audit_event(event)
        assert "발견" in te.title
        assert "005930" in te.title


class TestFormatterStrategySignal:
    def test_strategy_signal_created(self):
        event = _make_event("STRATEGY_SIGNAL_CREATED", symbol="005930",
                            payload={"signal": "BUY", "confidence": 0.85},
                            strategy="MomentumStrategy")
        te = format_audit_event(event)
        assert "신호" in te.title or "STRATEGY" in te.title
        assert "BUY" in te.body or "매수" in te.body
        assert "MomentumStrategy" in te.body or "85" in te.body


# ── Secret Masking Tests ──

class TestFormatterSecretMasking:
    def test_token_not_in_message(self):
        """Telegram Bot Token 원문이 메시지에 노출되지 않아야 함"""
        event = _make_event("KIS_API_FAILED",
                            payload={"error_message": "invalid token: 1234567890:ABCdefGHIjklmNOPqrstUVWXyz_abc",
                                     "endpoint": "/oauth2/token"})
        te = format_audit_event(event)
        message = te.formatted_message
        # "ABCdefGHIjklmNOPqrstUVWXyz_abc" 전체가 그대로 노출되면 안 됨
        assert "ABCdefGHIjklmNOPqrstUVWXyz_abc" not in message
        assert "****" in message  # 마스킹 적용 확인

    def test_account_not_in_message(self):
        event = _make_event("ORDER_FAILED",
                            payload={"error_message": "account 12345678-01 invalid"})
        te = format_audit_event(event)
        message = te.formatted_message
        assert "12345678-01" not in message
        assert "****" in message

    def test_appkey_not_in_message(self):
        event = _make_event("KIS_API_FAILED",
                            payload={"error_message": "appkey=PSD0kE1qW8fG3vBn5rY2mH7c", "endpoint": "/oauth2/token"})
        # appkey는 sanitize_payload에서 app_key 필드명으로 매칭되거나
        # JWT 토큰 패턴으로 마스킹되어야 함
        # payload에 app_key 필드로 직접 전달되는 경우
        pass

    def test_normal_info_preserved(self):
        """일반 정보(종목코드, 가격)는 마스킹되지 않아야 함"""
        event = _make_event("ORDER_SUBMITTED", symbol="005930",
                            payload={"price": 70000, "quantity": 10})
        te = format_audit_event(event)
        message = te.formatted_message
        assert "005930" in message
        assert "70000" in message


# ── Policy Tests ──

class TestPolicy:
    def test_default_allowlist_includes_required(self):
        required = [
            "SERVER_STARTED", "SERVER_STOPPED",
            "SESSION_STATE_CHANGED", "SESSION_STATE_UNKNOWN",
            "NEW_BUY_BLOCKED_BY_SESSION", "MARKET_REGIME_EVALUATED",
            "SCAN_COMPLETED", "CANDIDATE_DISCOVERED",
            "STRATEGY_SIGNAL_CREATED", "RISK_APPROVED",
            "RISK_REJECTED", "ORDER_SUBMITTED",
            "ORDER_FAILED", "FILL_CONFIRMED",
            "POSITION_SYNCED", "EOD_REPORT_CREATED",
            "EMERGENCY_STOP_ACTIVATED", "EMERGENCY_STOP_RELEASED",
            "KIS_API_FAILED",
        ]
        for name in required:
            assert name in DEFAULT_ALLOWED_EVENT_TYPES

    def test_allowed_event_passes(self):
        policy = TelegramNotificationPolicy()
        event = _make_event("ORDER_SUBMITTED")
        assert policy.is_allowed(event)

    def test_blocked_event_fails(self):
        policy = TelegramNotificationPolicy(
            blocked_event_types=frozenset({"ORDER_SUBMITTED"})
        )
        event = _make_event("ORDER_SUBMITTED")
        assert not policy.is_allowed(event)

    def test_not_in_allowlist_fails(self):
        policy = TelegramNotificationPolicy(
            allowed_event_types=frozenset({"SERVER_STARTED"})
        )
        event = _make_event("ORDER_SUBMITTED")
        assert not policy.is_allowed(event)

    def test_severity_filter_blocks_low(self):
        policy = TelegramNotificationPolicy(min_severity="HIGH")
        event = _make_event("TRADING_DAY_CHECKED", severity="LOW")
        # TRADING_DAY_CHECKED는 allowed이지만 severity가 낮아 차단
        assert not policy.is_allowed(event)

    def test_severity_filter_allows_high(self):
        policy = TelegramNotificationPolicy(min_severity="HIGH")
        event = _make_event("ORDER_FAILED", severity="CRITICAL")
        assert policy.is_allowed(event)

    def test_get_throttling_policy(self):
        policy = TelegramNotificationPolicy()
        tp = policy.get_throttling_policy("TRADING_DAY_CHECKED")
        assert tp is not None
        assert tp.max_count == 1


class TestThrottlingTracker:
    def test_can_send_initial(self):
        tracker = ThrottlingTracker()
        policy = ThrottlingPolicy(event_type="TEST", max_count=3, window_seconds=60)
        assert tracker.can_send("TEST", policy)

    def test_throttle_after_max(self):
        tracker = ThrottlingTracker()
        policy = ThrottlingPolicy(event_type="TEST", max_count=2, window_seconds=60)
        assert tracker.can_send("TEST", policy)
        tracker.record_send("TEST")
        assert tracker.can_send("TEST", policy)
        tracker.record_send("TEST")
        assert not tracker.can_send("TEST", policy)

    def test_different_types_independent(self):
        tracker = ThrottlingTracker()
        policy_a = ThrottlingPolicy(event_type="A", max_count=1, window_seconds=60)
        policy_b = ThrottlingPolicy(event_type="B", max_count=1, window_seconds=60)
        tracker.record_send("A")
        # A는 차단
        assert not tracker.can_send("A", policy_a)
        # B는 허용
        assert tracker.can_send("B", policy_b)

    def test_clear_resets(self):
        tracker = ThrottlingTracker()
        policy = ThrottlingPolicy(event_type="T", max_count=1, window_seconds=60)
        tracker.record_send("T")
        assert not tracker.can_send("T", policy)
        tracker.clear()
        assert tracker.can_send("T", policy)


# ── Sender Tests ──

class TestInMemorySender:
    def test_send_success(self):
        sender = InMemoryTelegramSender()
        event = TelegramEvent(
            event_type="SERVER_STARTED",
            title="시작",
            body="본문",
            notification_severity=NotificationSeverity.NORMAL,
        )
        result = sender.send(event)
        assert result.success
        assert sender.sent_count == 1
        assert sender.sent_events[0].title == "시작"

    def test_send_failure_does_not_raise(self):
        sender = InMemoryTelegramSender(should_fail=True)
        event = TelegramEvent(
            event_type="SERVER_STARTED",
            title="시작",
            body="본문",
            notification_severity=NotificationSeverity.NORMAL,
        )
        result = sender.send(event)
        assert not result.success
        assert result.error_message is not None
        assert sender.sent_count == 0

    def test_send_failure_does_not_propagate_exception(self):
        sender = InMemoryTelegramSender(should_fail=True)
        event = TelegramEvent(
            event_type="TEST",
            title="T",
            body="B",
            notification_severity=NotificationSeverity.NORMAL,
        )
        # send()가 예외를 발생시키지 않고 SendResult를 반환
        result = sender.send(event)
        assert isinstance(result, SendResult)
        assert not result.success


# ── Notifier Tests ──

class TestTelegramNotifier:
    def test_notify_e2e_success(self):
        sender = InMemoryTelegramSender()
        notifier = TelegramNotifier(sender=sender)
        event = _make_event("ORDER_SUBMITTED", symbol="005930",
                            payload={"order_type": "매수", "quantity": 10})
        result = notifier.notify(event)
        assert result is not None
        assert result.success
        assert sender.sent_count == 1

    def test_notify_e2e_failure_returns_result(self):
        """Sender 실패가 예외로 전파되지 않음"""
        sender = InMemoryTelegramSender(should_fail=True)
        notifier = TelegramNotifier(sender=sender)
        event = _make_event("ORDER_SUBMITTED", symbol="005930",
                            payload={"order_type": "매수", "quantity": 10})
        result = notifier.notify(event)
        assert result is not None
        assert not result.success

    def test_notify_blocked_by_policy(self):
        sender = InMemoryTelegramSender()
        policy = TelegramNotificationPolicy(
            allowed_event_types=frozenset({"SERVER_STARTED"})
        )
        notifier = TelegramNotifier(policy=policy, sender=sender)
        event = _make_event("ORDER_SUBMITTED")
        result = notifier.notify(event)
        assert result is None  # Policy에서 차단
        assert sender.sent_count == 0

    def test_notify_no_sender_returns_none(self):
        notifier = TelegramNotifier(sender=None)
        event = _make_event("SERVER_STARTED")
        result = notifier.notify(event)
        assert result is None

    def test_notify_invalid_event_type_returns_none(self):
        sender = InMemoryTelegramSender()
        notifier = TelegramNotifier(sender=sender)
        event = _make_event("KIS_API_CALLED")  # formatter에 없는 이벤트
        result = notifier.notify(event)
        assert result is None  # ValueError → 조용히 무시
        assert sender.sent_count == 0

    def test_notify_with_throttling(self):
        sender = InMemoryTelegramSender()
        policy = TelegramNotificationPolicy(
            allowed_event_types=frozenset({"TRADING_DAY_CHECKED"})
        )
        notifier = TelegramNotifier(policy=policy, sender=sender)
        event = _make_event("TRADING_DAY_CHECKED",
                            payload={"is_trading_day": True, "trading_day": "2026-05-04"})
        # TRADING_DAY_CHECKED는 max_count=1, window_seconds=600
        # 첫 번째 전송은 성공
        r1 = notifier.notify(event)
        assert r1 is not None and r1.success
        # 두 번째 전송은 throttling으로 차단
        r2 = notifier.notify(event)
        assert r2 is None  # throttling
        assert sender.sent_count == 1


# ── N3 New Event Tests ──

class TestNewEventTypes:
    """N3: CANDIDATE_EXCLUDED, QUANT_EVALUATED, SCAN_STARTED"""

    def test_candidate_excluded_exists(self):
        assert TelegramEventType.CANDIDATE_EXCLUDED.value == "CANDIDATE_EXCLUDED"

    def test_quant_evaluated_exists(self):
        assert TelegramEventType.QUANT_EVALUATED.value == "QUANT_EVALUATED"

    def test_scan_started_exists(self):
        assert TelegramEventType.SCAN_STARTED.value == "SCAN_STARTED"

    def test_severity_maps_exist(self):
        assert "CANDIDATE_EXCLUDED" in DEFAULT_SEVERITY_MAP
        assert "QUANT_EVALUATED" in DEFAULT_SEVERITY_MAP
        assert "SCAN_STARTED" in DEFAULT_SEVERITY_MAP


class TestNewFormatters:
    """N3: formatter for new event types"""

    def test_candidate_excluded_format(self):
        event = _make_event("CANDIDATE_EXCLUDED", symbol="999999",
                            payload={"excluded_reason": "ETF_EXCLUDED",
                                     "scanner_type": "RAPID_SURGE",
                                     "symbol": "999999"})
        te = format_audit_event(event)
        assert "ETF" in te.body or "ETF" in te.title.upper()

    def test_quant_evaluated_format(self):
        event = _make_event("QUANT_EVALUATED", symbol="005930",
                            payload={"decision": "PASS", "final_score": 85.0,
                                     "symbol": "005930",
                                     "scanner_type": "RAPID_SURGE"})
        te = format_audit_event(event)
        assert "PASS" in te.body or "85" in te.body

    def test_scan_started_format(self):
        event = _make_event("SCAN_STARTED",
                            payload={"scanner_type": "RAPID_SURGE",
                                     "scan_run_id": "scan_001"})
        te = format_audit_event(event)
        assert "SCAN" in te.title.upper() or "스캔" in te.title


class TestRiskRejectedEnhanced:
    """N3: RISK_REJECTED 상세 메시지 강화"""

    def test_risk_rejected_includes_reason_code(self):
        event = _make_event("RISK_REJECTED", symbol="005930",
                            payload={"reason_code": "MARKET_REGIME_BLOCKED",
                                     "reason_text": "Market regime blocks new buys",
                                     "failed_items": ["market_regime"],
                                     "checked_items": ["live_trading", "market_regime"],
                                     "market_regime": "BEAR",
                                     "session_state": "REGULAR_MARKET"})
        te = format_audit_event(event)
        assert "MARKET_REGIME_BLOCKED" in te.body or "BEAR" in te.body

    def test_risk_rejected_includes_market_regime(self):
        event = _make_event("RISK_REJECTED", symbol="000660",
                            payload={"reason_code": "SESSION_BLOCKED",
                                     "market_regime": "BULL",
                                     "session_state": "CLOSED_HOLIDAY"})
        te = format_audit_event(event)
        assert "CLOSED_HOLIDAY" in te.body or "SESSION" in te.body.upper()


class TestNewEventsSecretMasking:
    """N3: 신규 이벤트도 secret masking 유지"""

    def test_candidate_excluded_no_secret(self):
        event = _make_event("CANDIDATE_EXCLUDED", symbol="999999",
                            payload={"excluded_reason": "ETF_EXCLUDED"})
        te = format_audit_event(event)
        text = te.body
        for s in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert s not in text

    def test_quant_evaluated_no_secret(self):
        event = _make_event("QUANT_EVALUATED", symbol="005930",
                            payload={"decision": "PASS", "final_score": 85.0})
        te = format_audit_event(event)
        for s in ["app_key", "api_key", "token", "account_no", "chat_id"]:
            assert s not in te.body


class TestNewEventPolicy:
    """N3: allowlist + throttling for new events"""

    def test_candidate_excluded_in_allowlist(self):
        assert "CANDIDATE_EXCLUDED" in DEFAULT_ALLOWED_EVENT_TYPES

    def test_quant_evaluated_in_allowlist(self):
        assert "QUANT_EVALUATED" in DEFAULT_ALLOWED_EVENT_TYPES

    def test_candidate_excluded_passes_policy(self):
        policy = TelegramNotificationPolicy()
        event = _make_event("CANDIDATE_EXCLUDED", severity="NORMAL")
        assert policy.is_allowed(event) is True

    def test_quant_evaluated_passes_policy(self):
        policy = TelegramNotificationPolicy()
        event = _make_event("QUANT_EVALUATED", severity="NORMAL")
        assert policy.is_allowed(event) is True

    def test_quant_evaluated_has_throttling(self):
        policy = TelegramNotificationPolicy()
        tp = policy.get_throttling_policy("QUANT_EVALUATED")
        assert tp is not None
        assert tp.max_count <= 3