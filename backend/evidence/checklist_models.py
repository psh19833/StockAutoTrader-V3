"""Checklist schema/models for SAT3 evaluation evidence (read-only).

Backend is the single source of truth for checklist schema + results.
Frontend must NOT hardcode item definitions; it only renders.

This schema is shared by:
- Audit Timeline event payload evidence
- Evidence Card rendering

Secrets must never be included in checklist payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


CHECKLIST_SCHEMA_VERSION = "1.0"


class ChecklistStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True)
class ChecklistItem:
    """Single checklist item.

    Required fields (CEO confirmed):
      - key, label, status, value, threshold, reason, source, evaluated_at
    """

    key: str
    label: str
    status: ChecklistStatus

    value: Any = None
    threshold: Any = None
    reason: str = ""
    source: str = ""

    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Extensibility: front must safely render unknown fields
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChecklistResult:
    """Checklist evaluation result.

    schema_version is required and must be included.
    checklist items can vary by scanner_type / strategy_type / risk_rule_type.
    """

    schema_version: str = CHECKLIST_SCHEMA_VERSION

    # Context for dynamic item sets
    scanner_type: Optional[str] = None
    strategy_type: Optional[str] = None
    risk_rule_type: Optional[str] = None

    # Identity / traceability
    correlation_id: str = ""
    stage: str = ""  # e.g., SCANNER / QUANT / RISK / SAFETY_GATE

    items: list[ChecklistItem] = field(default_factory=list)

    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # datetime → isoformat
        d["evaluated_at"] = self.evaluated_at.isoformat()
        d["items"] = [
            {
                **{k: v for k, v in asdict(it).items() if k != "evaluated_at"},
                "evaluated_at": it.evaluated_at.isoformat(),
                # status is Enum
                "status": it.status.value,
            }
            for it in self.items
        ]
        return d
