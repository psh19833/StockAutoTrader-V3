"""Scanner Audit — Scanner 관련 AuditEvent 변환"""
from __future__ import annotations

from audit_logging.audit_event import AuditEvent, AuditEventType

from scanner.scanner_types import ScannerType
from scanner.candidate import ScannerCandidate
from scanner.scan_result import ScanRunResult


def build_scan_started_event(
    scan_run_id: str,
    scanner_type: ScannerType,
    market_regime: str,
) -> AuditEvent:
    """SCAN_STARTED AuditEvent 생성"""
    return AuditEvent(
        event_type=AuditEventType.SCAN_STARTED.value,
        severity="INFO",
        payload={
            "scan_run_id": scan_run_id,
            "scanner_type": scanner_type.value,
            "market_regime": market_regime,
        },
        source="scanner",
    )


def build_scan_completed_event(result: ScanRunResult) -> AuditEvent:
    """SCAN_COMPLETED AuditEvent 생성"""
    return AuditEvent(
        event_type=AuditEventType.SCAN_COMPLETED.value,
        severity="INFO",
        payload={
            "scan_run_id": result.scan_run_id,
            "scanner_type": result.scanner_type.value,
            "market_regime": result.market_regime,
            "collected_count": result.collected_count,
            "excluded_count": result.excluded_count,
            "included_count": result.included_count,
            "candidate_count": len(result.candidates),
        },
        source="scanner",
    )


def build_candidate_discovered_event(candidate: ScannerCandidate) -> AuditEvent:
    """CANDIDATE_DISCOVERED AuditEvent 생성"""
    from evidence.checklist_mappers import scanner_candidate_to_checklist

    payload = dict(candidate.metrics)
    payload.update({
        "symbol_name": candidate.symbol_name,
        "scanner_type": candidate.scanner_type.value,
        "scan_run_id": candidate.scan_run_id,
        "discovered_reason": candidate.discovered_reason,
        # Evidence checklist (schema + result)
        "checklist": scanner_candidate_to_checklist(candidate).to_dict(),
    })
    return AuditEvent(
        event_type=AuditEventType.CANDIDATE_DISCOVERED.value,
        severity="INFO",
        symbol=candidate.symbol,
        payload=payload,
        source="scanner",
    )


def build_candidate_excluded_event(candidate: ScannerCandidate) -> AuditEvent:
    """CANDIDATE_EXCLUDED AuditEvent 생성"""
    from evidence.checklist_mappers import scanner_candidate_to_checklist

    payload = dict(candidate.metrics)
    payload.update({
        "symbol_name": candidate.symbol_name,
        "scanner_type": candidate.scanner_type.value,
        "scan_run_id": candidate.scan_run_id,
        "excluded_reason": candidate.excluded_reason,
        # Evidence checklist (schema + result)
        "checklist": scanner_candidate_to_checklist(candidate).to_dict(),
    })
    return AuditEvent(
        event_type=AuditEventType.CANDIDATE_EXCLUDED.value,
        severity="INFO",
        symbol=candidate.symbol,
        payload=payload,
        source="scanner",
    )