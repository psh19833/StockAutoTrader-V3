"""TelegramFormatter — AuditEvent → TelegramEvent 변환

각 AuditEventType을 텔레그램 알림 메시지로 변환한다.
메시지 본문에 secret/token/account 원문이 노출되지 않도록 보장한다.
"""
from __future__ import annotations

from audit_logging.audit_event import AuditEvent
from audit_logging.log_sanitizer import sanitize_payload
from notifications.telegram_event import (
    TelegramEvent,
    TelegramEventType,
    NotificationSeverity,
    DEFAULT_SEVERITY_MAP,
)


def _sanitize_str(value: str) -> str:
    """AuditEvent payload 내의 민감값을 sanitize하여 문자열로 변환"""
    from audit_logging.log_sanitizer import sanitize_value
    result = sanitize_value("message", value)
    return str(result) if not isinstance(result, str) else result


def _severity_from_event(event: AuditEvent) -> NotificationSeverity:
    """AuditEvent의 severity로 NotificationSeverity 추정"""
    audit_sev = event.severity.upper()
    if audit_sev == "CRITICAL":
        return NotificationSeverity.CRITICAL
    elif audit_sev == "ERROR":
        return NotificationSeverity.HIGH
    elif audit_sev == "WARNING":
        return NotificationSeverity.HIGH
    return DEFAULT_SEVERITY_MAP.get(event.event_type, NotificationSeverity.NORMAL)


def _format_payload(payload: dict) -> str:
    """payload를 읽기 쉬운 문자열로 변환"""
    if not payload:
        return ""
    lines: list[str] = []
    for k, v in payload.items():
        sv = _sanitize_str(str(v) if not isinstance(v, str) else v)
        lines.append(f"  {k}: {sv}")
    return "\n" + "\n".join(lines)


def _format_order_submitted(event: AuditEvent) -> TelegramEvent:
    title = f"📤 주문 제출 — {event.symbol or '(종목 미지정)'}"
    body = f"주문이 제출되었습니다."
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    pl = event.payload or {}
    if "order_type" in pl:
        body += f"\n  유형: {pl['order_type']}"
    if "quantity" in pl:
        body += f"\n  수량: {pl['quantity']}"
    if "price" in pl:
        body += f"\n  가격: {pl['price']}"
    if event.strategy_name:
        body += f"\n  전략: {event.strategy_name}"
    body += _format_payload({k: v for k, v in pl.items()
                             if k not in ("order_type", "quantity", "price")})
    return TelegramEvent(
        event_type=TelegramEventType.ORDER_SUBMITTED.value,
        title=title,
        body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_fill_confirmed(event: AuditEvent) -> TelegramEvent:
    title = f"✅ 체결 완료 — {event.symbol or '(종목 미지정)'}"
    body = f"주문이 체결되었습니다."
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    pl = event.payload or {}
    if "filled_quantity" in pl:
        body += f"\n  체결수량: {pl['filled_quantity']}"
    if "filled_price" in pl:
        body += f"\n  체결가격: {pl['filled_price']}"
    if "order_type" in pl:
        body += f"\n  주문유형: {pl['order_type']}"
    if event.strategy_name:
        body += f"\n  전략: {event.strategy_name}"
    body += _format_payload({k: v for k, v in pl.items()
                             if k not in ("filled_quantity", "filled_price", "order_type")})
    return TelegramEvent(
        event_type=TelegramEventType.FILL_CONFIRMED.value,
        title=title,
        body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_server_started(event: AuditEvent) -> TelegramEvent:
    title = "🚀 SAT3 서버 시작"
    body = f"SAT3 서버가 시작되었습니다."
    pl = event.payload or {}
    if "mode" in pl:
        body += f"\n  모드: {pl['mode']}"
    if "trading_day" in pl:
        body += f"\n  거래일: {pl['trading_day']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.SERVER_STARTED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_server_stopped(event: AuditEvent) -> TelegramEvent:
    title = "🛑 SAT3 서버 중지"
    body = "SAT3 서버가 중지되었습니다."
    pl = event.payload or {}
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.SERVER_STOPPED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_trading_day_checked(event: AuditEvent) -> TelegramEvent:
    title = "📅 거래일 확인"
    pl = event.payload or {}
    trading_day = event.trading_day or pl.get("trading_day", "(알 수 없음)")
    body = f"거래일: {trading_day}"
    if "is_trading_day" in pl:
        is_td = pl["is_trading_day"]
        body += f"\n  영업일 여부: {'✅ 영업일' if is_td else '❌ 휴장일'}"
    body += _format_payload({k: v for k, v in pl.items()
                             if k not in ("trading_day", "is_trading_day")})
    return TelegramEvent(
        event_type=TelegramEventType.TRADING_DAY_CHECKED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.LOW,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_session_state_changed(event: AuditEvent) -> TelegramEvent:
    pl = event.payload or {}
    prev = pl.get("previous_state", "(없음)")
    curr = pl.get("current_state", "(알 수 없음)")
    title = f"🔄 세션 상태 변경"
    body = f"  이전: {prev}\n  현재: {curr}"
    if "trading_day" in pl:
        body += f"\n  거래일: {pl['trading_day']}"
    body += _format_payload({k: v for k, v in pl.items()
                             if k not in ("previous_state", "current_state", "trading_day")})
    return TelegramEvent(
        event_type=TelegramEventType.SESSION_STATE_CHANGED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_session_state_unknown(event: AuditEvent) -> TelegramEvent:
    title = "❓ 세션 상태 알 수 없음"
    pl = event.payload or {}
    body = "KIS API 응답에서 세션 상태를 확인할 수 없습니다."
    if "response_code" in pl:
        body += f"\n  응답코드: {_sanitize_str(str(pl['response_code']))}"
    if "message" in pl:
        body += f"\n  메시지: {_sanitize_str(str(pl['message']))}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.SESSION_STATE_UNKNOWN.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.CRITICAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_new_buy_blocked(event: AuditEvent) -> TelegramEvent:
    title = "🚫 신규 매수 차단"
    pl = event.payload or {}
    body = f"세션 정책에 의해 신규 매수가 차단되었습니다."
    if "session_state" in pl:
        body += f"\n  현재 세션: {pl['session_state']}"
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.NEW_BUY_BLOCKED_BY_SESSION.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_market_regime_evaluated(event: AuditEvent) -> TelegramEvent:
    pl = event.payload or {}
    regime = pl.get("regime", "(알 수 없음)")
    title = f"📊 시장 국면 평가"
    body = f"  국면: {regime}"
    if "score" in pl:
        body += f"\n  점수: {pl['score']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.MARKET_REGIME_EVALUATED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_scan_completed(event: AuditEvent) -> TelegramEvent:
    pl = event.payload or {}
    total = pl.get("total_candidates", "?")
    title = f"🔍 스캔 완료"
    body = f"전체 스캔이 완료되었습니다.\n  후보 종목: {total}개"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.SCAN_COMPLETED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_candidate_discovered(event: AuditEvent) -> TelegramEvent:
    title = f"💡 종목 발견 — {event.symbol or '(종목 미지정)'}"
    body = "새로운 매수 후보 종목이 발견되었습니다."
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    pl = event.payload or {}
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.CANDIDATE_DISCOVERED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_strategy_signal_created(event: AuditEvent) -> TelegramEvent:
    title = f"📈 전략 신호 발생 — {event.symbol or '(종목 미지정)'}"
    body = "전략이 매수/매도 신호를 생성했습니다."
    pl = event.payload or {}
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    if "signal" in pl:
        body += f"\n  신호: {pl['signal']}"
    if "confidence" in pl:
        body += f"\n  신뢰도: {pl['confidence']}"
    if event.strategy_name:
        body += f"\n  전략: {event.strategy_name}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.STRATEGY_SIGNAL_CREATED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_risk_approved(event: AuditEvent) -> TelegramEvent:
    title = f"✅ 리스크 승인 — {event.symbol or '(종목 미지정)'}"
    body = "리스크 심사를 통과했습니다."
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    pl = event.payload or {}
    if "risk_score" in pl:
        body += f"\n  리스크 점수: {pl['risk_score']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.RISK_APPROVED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_risk_rejected(event: AuditEvent) -> TelegramEvent:
    title = f"❌ 리스크 기각 — {event.symbol or '(종목 미지정)'}"
    body = "리스크 심사에서 기각되었습니다."
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    pl = event.payload or {}
    if "risk_score" in pl:
        body += f"\n  리스크 점수: {pl['risk_score']}"
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.RISK_REJECTED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_order_failed(event: AuditEvent) -> TelegramEvent:
    title = f"🚨 주문 실패 — {event.symbol or '(종목 미지정)'}"
    body = "주문 전송에 실패했습니다."
    if event.symbol:
        body += f"\n  종목: {event.symbol}"
    pl = event.payload or {}
    if "error_code" in pl:
        body += f"\n  에러코드: {_sanitize_str(str(pl['error_code']))}"
    if "error_message" in pl:
        body += f"\n  에러메시지: {_sanitize_str(str(pl['error_message']))}"
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.ORDER_FAILED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.CRITICAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_position_synced(event: AuditEvent) -> TelegramEvent:
    title = "📋 포지션 동기화"
    pl = event.payload or {}
    body = "보유 포지션이 동기화되었습니다."
    if "symbol_count" in pl:
        body += f"\n  종목 수: {pl['symbol_count']}"
    if "total_value" in pl:
        body += f"\n  총 평가액: {pl['total_value']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.POSITION_SYNCED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.LOW,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_eod_report_created(event: AuditEvent) -> TelegramEvent:
    title = "📊 EOD 리포트 생성"
    pl = event.payload or {}
    trading_day = event.trading_day or pl.get("trading_day", "(알 수 없음)")
    body = f"장 마감 리포트가 생성되었습니다.\n  거래일: {trading_day}"
    if "summary" in pl:
        body += f"\n  요약: {pl['summary']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.EOD_REPORT_CREATED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.NORMAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_emergency_stop_activated(event: AuditEvent) -> TelegramEvent:
    title = "🆘 비상정지 활성화"
    pl = event.payload or {}
    body = "비상정지가 활성화되어 모든 주문이 차단됩니다."
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.EMERGENCY_STOP_ACTIVATED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.CRITICAL,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_emergency_stop_released(event: AuditEvent) -> TelegramEvent:
    title = "✅ 비상정지 해제"
    pl = event.payload or {}
    body = "비상정지가 해제되었습니다."
    if "reason" in pl:
        body += f"\n  사유: {pl['reason']}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.EMERGENCY_STOP_RELEASED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


def _format_kis_api_failed(event: AuditEvent) -> TelegramEvent:
    title = "⚠️ KIS API 오류"
    pl = event.payload or {}
    body = "KIS API 호출 중 오류가 발생했습니다."
    if "endpoint" in pl:
        body += f"\n  엔드포인트: {pl['endpoint']}"
    if "error_code" in pl:
        body += f"\n  에러코드: {_sanitize_str(str(pl['error_code']))}"
    if "error_message" in pl:
        body += f"\n  메시지: {_sanitize_str(str(pl['error_message']))}"
    body += _format_payload(pl)
    return TelegramEvent(
        event_type=TelegramEventType.KIS_API_FAILED.value,
        title=title, body=body,
        notification_severity=NotificationSeverity.HIGH,
        correlation_id=event.correlation_id,
        source_audit_event_id=event.event_id,
    )


# Formatter 디스패치 맵
_FORMATTER_MAP: dict[str, callable] = {
    "SERVER_STARTED": _format_server_started,
    "SERVER_STOPPED": _format_server_stopped,
    "TRADING_DAY_CHECKED": _format_trading_day_checked,
    "SESSION_STATE_CHANGED": _format_session_state_changed,
    "SESSION_STATE_UNKNOWN": _format_session_state_unknown,
    "NEW_BUY_BLOCKED_BY_SESSION": _format_new_buy_blocked,
    "MARKET_REGIME_EVALUATED": _format_market_regime_evaluated,
    "SCAN_COMPLETED": _format_scan_completed,
    "CANDIDATE_DISCOVERED": _format_candidate_discovered,
    "STRATEGY_SIGNAL_CREATED": _format_strategy_signal_created,
    "RISK_APPROVED": _format_risk_approved,
    "RISK_REJECTED": _format_risk_rejected,
    "ORDER_SUBMITTED": _format_order_submitted,
    "ORDER_FAILED": _format_order_failed,
    "FILL_CONFIRMED": _format_fill_confirmed,
    "POSITION_SYNCED": _format_position_synced,
    "EOD_REPORT_CREATED": _format_eod_report_created,
    "EMERGENCY_STOP_ACTIVATED": _format_emergency_stop_activated,
    "EMERGENCY_STOP_RELEASED": _format_emergency_stop_released,
    "KIS_API_FAILED": _format_kis_api_failed,
}


def format_audit_event(event: AuditEvent) -> TelegramEvent:
    """AuditEvent → TelegramEvent 변환

    Args:
        event: 변환할 AuditEvent

    Returns:
        변환된 TelegramEvent

    Raises:
        ValueError: 지원하지 않는 AuditEventType인 경우
    """
    formatter = _FORMATTER_MAP.get(event.event_type)
    if formatter is None:
        raise ValueError(f"지원하지 않는 AuditEventType: {event.event_type}")
    return formatter(event)