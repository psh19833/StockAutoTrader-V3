"""Checklist mappers: domain objects -> ChecklistResult.

- Scanner / Quant / Risk / SafetyGate outputs are converted to a unified checklist schema.
- Do not include secrets, raw REST responses, or raw WebSocket full messages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from evidence.checklist_models import (
    ChecklistItem,
    ChecklistResult,
    ChecklistStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def scanner_candidate_to_checklist(candidate: Any) -> ChecklistResult:
    """ScannerCandidate -> ChecklistResult (SCANNER stage)."""
    # candidate is scanner.candidate.ScannerCandidate
    scanner_type = getattr(getattr(candidate, "scanner_type", None), "value", None)
    correlation_id = getattr(candidate, "scan_run_id", "") or ""

    items: list[ChecklistItem] = []

    included = bool(getattr(candidate, "included", True))
    excluded_reason = getattr(candidate, "excluded_reason", None)

    items.append(
        ChecklistItem(
            key="scanner.included",
            label="Scanner 후보 편입 여부",
            status=ChecklistStatus.PASS if included else ChecklistStatus.FAIL,
            value=included,
            threshold=True,
            reason="" if included else (excluded_reason or "excluded"),
            source="scanner",
            evaluated_at=_now(),
        )
    )

    items.append(
        ChecklistItem(
            key="scanner.product_type",
            label="상품 유형 (COMMON_STOCK)",
            status=ChecklistStatus.PASS,
            value=getattr(candidate, "product_type", None),
            threshold="COMMON_STOCK",
            reason="",
            source="scanner",
            evaluated_at=_now(),
        )
    )

    items.append(
        ChecklistItem(
            key="scanner.market",
            label="시장 (KOSPI/KOSDAQ)",
            status=ChecklistStatus.PASS,
            value=getattr(candidate, "market", None),
            threshold="KOSPI|KOSDAQ",
            reason="",
            source="scanner",
            evaluated_at=_now(),
        )
    )

    return ChecklistResult(
        stage="SCANNER",
        correlation_id=correlation_id,
        scanner_type=scanner_type,
        items=items,
        evaluated_at=_now(),
    )


def quant_score_to_checklist(score: Any) -> ChecklistResult:
    """QuantCandidateScore -> ChecklistResult (QUANT stage)."""
    correlation_id = getattr(score, "evaluation_id", "") or ""
    scanner_type = getattr(score, "scanner_type", None)

    decision = getattr(getattr(score, "decision", None), "value", None) or str(getattr(score, "decision", ""))
    final_score = float(getattr(score, "final_score", 0.0) or 0.0)

    # Threshold is intentionally generic at schema level; concrete thresholds live in ScoringConfig.
    # We still emit a readable value for UI.
    items: list[ChecklistItem] = [
        ChecklistItem(
            key="quant.decision",
            label="Quant 최종 판단",
            status=(ChecklistStatus.PASS if decision == "PASS" else ChecklistStatus.WARN if decision == "WATCH" else ChecklistStatus.FAIL),
            value=decision,
            threshold="PASS",
            reason="; ".join(list(getattr(score, "reasons", ()) or ()))[:500],
            source="quant",
            evaluated_at=_now(),
        ),
        ChecklistItem(
            key="quant.final_score",
            label="Quant 최종 점수",
            status=ChecklistStatus.INFO,
            value=final_score,
            threshold=None,
            reason="",
            source="quant",
            evaluated_at=_now(),
        ),
    ]

    return ChecklistResult(
        stage="QUANT",
        correlation_id=correlation_id,
        scanner_type=scanner_type,
        items=items,
        evaluated_at=_now(),
    )


def risk_decision_to_checklist(decision: Any) -> ChecklistResult:
    """RiskDecision -> ChecklistResult (RISK stage)."""
    correlation_id = getattr(decision, "correlation_id", "") or ""

    allowed = bool(getattr(decision, "allowed", False))
    reason_code = getattr(decision, "reason_code", "") or ""
    reason_text = getattr(decision, "reason_text", "") or ""

    items: list[ChecklistItem] = [
        ChecklistItem(
            key="risk.allowed",
            label="Risk Engine 주문 허용 여부",
            status=ChecklistStatus.PASS if allowed else ChecklistStatus.FAIL,
            value=allowed,
            threshold=True,
            reason=(reason_text or reason_code),
            source="risk",
            evaluated_at=_now(),
            meta={"reason_code": reason_code},
        )
    ]

    checked = list(getattr(decision, "checked_items", ()) or ())
    failed = list(getattr(decision, "failed_items", ()) or ())

    # Keep item-level list as compact metadata (do not explode into too many items yet)
    if checked:
        items.append(
            ChecklistItem(
                key="risk.checked_items",
                label="Risk 검증 완료 항목",
                status=ChecklistStatus.INFO,
                value=checked,
                threshold=None,
                reason="",
                source="risk",
                evaluated_at=_now(),
            )
        )

    if failed:
        items.append(
            ChecklistItem(
                key="risk.failed_items",
                label="Risk 실패 항목",
                status=ChecklistStatus.WARN if allowed else ChecklistStatus.FAIL,
                value=failed,
                threshold=None,
                reason=reason_code,
                source="risk",
                evaluated_at=_now(),
            )
        )

    return ChecklistResult(
        stage="RISK",
        correlation_id=correlation_id,
        items=items,
        evaluated_at=_now(),
    )


def safety_gate_result_to_checklist(result: Any, correlation_id: str = "") -> ChecklistResult:
    """SafetyGateResult -> ChecklistResult (SAFETY_GATE stage)."""
    items: list[ChecklistItem] = []

    checks = list(getattr(result, "checks", []) or [])
    for c in checks:
        name = getattr(c, "name", "")
        passed = bool(getattr(c, "passed", False))
        reason = getattr(c, "reason", "")
        items.append(
            ChecklistItem(
                key=f"safety.{name}",
                label=f"SafetyGate: {name}",
                status=ChecklistStatus.PASS if passed else ChecklistStatus.FAIL,
                value=passed,
                threshold=True,
                reason="" if passed else (reason or "failed"),
                source="safety_gate",
                evaluated_at=_now(),
            )
        )

    passed_all = bool(getattr(result, "passed", False))
    items.insert(
        0,
        ChecklistItem(
            key="safety.passed",
            label="SafetyGate 전체 통과",
            status=ChecklistStatus.PASS if passed_all else ChecklistStatus.FAIL,
            value=passed_all,
            threshold=True,
            reason="; ".join(list(getattr(result, "block_reasons", []) or []))[:500],
            source="safety_gate",
            evaluated_at=_now(),
        ),
    )

    return ChecklistResult(
        stage="SAFETY_GATE",
        correlation_id=correlation_id,
        items=items,
        evaluated_at=_now(),
    )
