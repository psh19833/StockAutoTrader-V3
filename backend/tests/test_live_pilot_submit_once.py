import json
from pathlib import Path

import pytest

from scripts.live_pilot_submit_once import (
    CONFIRM_STRING,
    PilotGuardError,
    guard_and_submit_once,
)


class MockSubmitter:
    def __init__(self, success=True, order_number="ODNO123", message="OK"):
        self.calls = 0
        self.success = success
        self.order_number = order_number
        self.message = message

    class Resp:
        def __init__(self, success, order_number, message):
            self.success = success
            self.order_number = order_number
            self.message = message
            self.error_type = ""

    def submit_cash_order(self, payload, tr_id):
        self.calls += 1
        return MockSubmitter.Resp(self.success, self.order_number, self.message)


def _write_preview(tmp_path: Path, *, overrides=None):
    base = {
        "actual_order_submitted": False,
        "risk": {"allowed": True},
        "order_intent": {
            "symbol": "005930",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
        },
        "kis_payload_preview": {
            "PDNO": "005930",
            "ORD_DVSN": "01",
            "ORD_QTY": "1",
            "ORD_UNPR": "0",
            # Intentionally include sensitive-like fields to ensure redaction.
            "CANO": "44413716",
            "ACNT_PRDT_CD": "01",
        },
    }
    if overrides:
        # shallow merge is enough for tests
        for k, v in overrides.items():
            base[k] = v
    p = tmp_path / "preview.json"
    p.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    return p


def _session_ok():
    return True, "REGULAR_MARKET"


def _session_bad():
    return False, "SESSION_STATE_UNKNOWN"


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    # Arrange a fake project root with logs/ and .emergency_stop absent.
    (tmp_path / "logs").mkdir()
    return tmp_path


def test_no_confirm_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm="",
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "CONFIRM_MISMATCH"


def test_wrong_confirm_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm="NOPE",
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "CONFIRM_MISMATCH"


def test_missing_preview_blocks(project_root, tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=missing,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "PREVIEW_JSON_MISSING"


def test_actual_order_submitted_true_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path, overrides={"actual_order_submitted": True})
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "PREVIEW_ALREADY_SUBMITTED"


def test_risk_not_allowed_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path, overrides={"risk": {"allowed": False}})
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "RISK_NOT_ALLOWED"


def test_side_not_buy_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path, overrides={"order_intent": {"symbol": "005930", "side": "SELL", "quantity": 1, "order_type": "MARKET"}})
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "SIDE_NOT_BUY"


def test_qty_not_one_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path, overrides={"order_intent": {"symbol": "005930", "side": "BUY", "quantity": 2, "order_type": "MARKET"}})
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "QTY_NOT_ONE"


def test_order_type_not_market_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path, overrides={"order_intent": {"symbol": "005930", "side": "BUY", "quantity": 1, "order_type": "LIMIT"}})
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "ORDER_TYPE_NOT_MARKET"


def test_ord_dvsn_invalid_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    j = json.loads(preview.read_text(encoding="utf-8"))
    j["kis_payload_preview"]["ORD_DVSN"] = "00"
    preview.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "ORD_DVSN_INVALID"


def test_ord_unpr_invalid_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    j = json.loads(preview.read_text(encoding="utf-8"))
    j["kis_payload_preview"]["ORD_UNPR"] = "100"
    preview.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "ORD_UNPR_INVALID"


def test_pdno_symbol_mismatch_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    j = json.loads(preview.read_text(encoding="utf-8"))
    j["kis_payload_preview"]["PDNO"] = "000660"
    preview.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "PDNO_SYMBOL_MISMATCH"


def test_kill_switch_active_blocks(project_root, tmp_path):
    (project_root / ".emergency_stop").write_text("ACTIVE", encoding="utf-8")
    preview = _write_preview(tmp_path)
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "EMERGENCY_STOP_ACTIVE"


def test_lock_file_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    # Create the lock ahead of time
    lock = project_root / "logs" / "live_pilot_submit_once_20000101_005930_c1.lock"
    lock.write_text("locked", encoding="utf-8")

    # Patch datetime in module by forcing correlation id that maps to existing lock name would be hard.
    # Instead: just create any lock and then create expected lock by calling once and catching.
    # We take a simpler route: use correlation_id that will create a lock, pre-create it after computing artifacts.
    from scripts import live_pilot_submit_once as mod
    art = mod._artifacts(project_root, "005930", "c1")
    art.lock_path.write_text("locked", encoding="utf-8")

    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_ok,
        )
    assert e.value.code == "LOCK_EXISTS"


def test_session_not_regular_blocks(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    with pytest.raises(PilotGuardError) as e:
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm=CONFIRM_STRING,
            correlation_id="c1",
            submitter=MockSubmitter(),
            session_checker=_session_bad,
        )
    assert e.value.code == "SESSION_NOT_REGULAR"


def test_success_calls_submit_once_and_writes_files(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    sub = MockSubmitter(success=True, order_number="ODNO999", message="OK")
    out = guard_and_submit_once(
        project_root=project_root,
        preview_json_path=preview,
        confirm=CONFIRM_STRING,
        correlation_id="c999",
        submitter=sub,
        session_checker=_session_ok,
    )
    assert sub.calls == 1
    assert out["status"] == "SUBMITTED"
    # Artifacts created
    art = out["artifacts"]
    assert Path(art["lock"]).exists()
    assert Path(art["request"]).exists()
    assert Path(art["response"]).exists()
    assert Path(art["final"]).exists()
    # Redaction: request json should not contain CANO
    req = Path(art["request"]).read_text(encoding="utf-8")
    assert "44413716" not in req
    assert "[REDACTED]" in req


def test_failure_writes_error_final(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    sub = MockSubmitter(success=False, order_number="", message="REJECT")
    out = guard_and_submit_once(
        project_root=project_root,
        preview_json_path=preview,
        confirm=CONFIRM_STRING,
        correlation_id="c_fail",
        submitter=sub,
        session_checker=_session_ok,
    )
    assert sub.calls == 1
    assert out["status"] in {"REJECTED", "ERROR"}
    assert Path(out["artifacts"]["final"]).exists()


def test_allow_real_submit_does_not_build_factory_when_flag_false(project_root, tmp_path):
    preview = _write_preview(tmp_path)
    sub = MockSubmitter(success=True)

    built = {"count": 0}

    def factory():
        built["count"] += 1
        return sub

    _ = guard_and_submit_once(
        project_root=project_root,
        preview_json_path=preview,
        confirm=CONFIRM_STRING,
        correlation_id="c_factory0",
        submitter=sub,
        allow_real_submit=False,
        submitter_factory=factory,
        session_checker=_session_ok,
    )
    assert built["count"] == 0


def test_allow_real_submit_with_wrong_confirm_never_builds_factory(project_root, tmp_path):
    preview = _write_preview(tmp_path)

    built = {"count": 0}

    def factory():
        built["count"] += 1
        return MockSubmitter(success=True)

    with pytest.raises(PilotGuardError):
        guard_and_submit_once(
            project_root=project_root,
            preview_json_path=preview,
            confirm="NOPE",
            correlation_id="c_factory_bad",
            submitter=None,
            allow_real_submit=True,
            submitter_factory=factory,
            session_checker=_session_ok,
        )
    assert built["count"] == 0


def test_allow_real_submit_builds_factory_only_when_needed(project_root, tmp_path):
    preview = _write_preview(tmp_path)

    built = {"count": 0}
    sub = MockSubmitter(success=True, order_number="ODNO777", message="OK")

    def factory():
        built["count"] += 1
        return sub

    out = guard_and_submit_once(
        project_root=project_root,
        preview_json_path=preview,
        confirm=CONFIRM_STRING,
        correlation_id="c_factory1",
        submitter=None,
        allow_real_submit=True,
        submitter_factory=factory,
        session_checker=_session_ok,
    )
    assert built["count"] == 1
    assert out["status"] == "SUBMITTED"
    assert out["kis_order_number"] == "ODNO777"
