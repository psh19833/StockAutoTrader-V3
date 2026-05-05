from __future__ import annotations

from datetime import datetime

from evidence.checklist_models import ChecklistItem, ChecklistResult, ChecklistStatus, CHECKLIST_SCHEMA_VERSION


def test_checklist_item_required_fields_exist():
    item = ChecklistItem(
        key="k",
        label="l",
        status=ChecklistStatus.INFO,
        value=123,
        threshold=100,
        reason="r",
        source="s",
    )
    assert item.key == "k"
    assert item.label == "l"
    assert item.status.value in ("PASS", "FAIL", "WARN", "INFO")
    assert item.value == 123
    assert item.threshold == 100
    assert item.reason == "r"
    assert item.source == "s"
    assert isinstance(item.evaluated_at, datetime)


def test_checklist_result_includes_schema_version_and_items():
    result = ChecklistResult(
        stage="RISK",
        correlation_id="corr",
        items=[
            ChecklistItem(
                key="risk.allowed",
                label="allowed",
                status=ChecklistStatus.PASS,
                value=True,
                threshold=True,
                reason="",
                source="risk",
            )
        ],
    )
    d = result.to_dict()
    assert d["schema_version"] == CHECKLIST_SCHEMA_VERSION
    assert d["stage"] == "RISK"
    assert d["correlation_id"] == "corr"
    assert isinstance(d["items"], list)
    assert d["items"][0]["status"] == "PASS"
    # evaluated_at must be isoformat string
    assert isinstance(d["evaluated_at"], str)
    assert "T" in d["evaluated_at"]
