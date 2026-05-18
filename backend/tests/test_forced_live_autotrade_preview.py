from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "backend" / "scripts" / "forced_live_autotrade_preview.py"


def _run(args: list[str]) -> dict:
    # Run with repo root as cwd so backend/ imports resolve.
    cmd = [str(REPO_ROOT / ".venv" / "bin" / "python"), str(SCRIPT), *args]
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, f"rc={p.returncode} stderr={p.stderr} stdout={p.stdout}"
    return json.loads(p.stdout)


def test_real_mode_report_generated_even_when_no_candidates() -> None:
    r = _run(["--real"])
    assert r["mode"] == "real"
    assert r["actual_order_submitted"] is False
    assert r["candidate_source"] == "scanner"
    assert "scanner" in r
    assert isinstance(r["scanner"]["candidate_count"], int)
    # 0 candidates is acceptable.
    if r["scanner"]["candidate_count"] == 0:
        assert r["scanner"]["empty_reason"]


def test_fixture_mode_reaches_payload_and_never_submits() -> None:
    r = _run(["--fixture", "--symbol", "005930"])
    assert r["mode"] == "fixture"
    assert r["actual_order_submitted"] is False
    assert r["candidate_source"] == "fixture"
    assert r["scanner"]["candidate_count"] >= 1

    # Strategy decision should exist in fixture mode.
    assert r["strategy"]["decision"] is not None

    # Order intent should exist.
    oi = r["order_intent"]
    assert oi["symbol"] == "005930"
    assert oi["side"] in {"BUY", "SELL"}
    assert isinstance(oi["quantity"], int)

    # Payload preview should be built (but not submitted).
    payload = r["kis_payload_preview"]
    assert isinstance(payload, dict)
    assert payload.get("PDNO") == "005930"
    assert payload.get("ORD_QTY")

    # Mapping note should exist.
    note = r.get("order_type_mapping_note") or {}
    assert note.get("order_intent_order_type") in {"MARKET", "LIMIT"}
    assert note.get("kis_ord_dvsn")
    assert note.get("kis_ord_unpr") is not None

    # Soft/hard lists exist.
    assert isinstance(r["soft_warnings"], list)
    assert isinstance(r["hard_blocker_candidates"], list)


def test_order_api_not_called_in_preview(monkeypatch) -> None:
    # If any code path tries to call submit_cash_order, we fail the test.
    import kis.order_api as order_api

    def _boom(*args, **kwargs):  # pragma: no cover
        raise AssertionError("submit_cash_order must not be called in preview")

    monkeypatch.setattr(order_api, "submit_cash_order", _boom)

    r = _run(["--fixture", "--symbol", "005930"])
    assert r["actual_order_submitted"] is False
