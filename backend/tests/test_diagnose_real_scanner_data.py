from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_diagnose_real_scanner_data_is_readonly_and_explains_no_fresh_data(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "backend" / "scripts" / "diagnose_real_scanner_data.py"

    # Snapshot data/ before running: script must not create synthetic files.
    data_dir = repo_root / "data"
    before = set(data_dir.rglob("*") if data_dir.exists() else [])

    cmd = [str(repo_root / ".venv" / "bin" / "python"), str(script)]
    out = subprocess.check_output(cmd, text=True)
    j = json.loads(out)

    assert j["actual_order_submitted"] is False
    assert j["live_start_called"] is False
    assert j["runtime_tick_called"] is False

    # Under default config, REST provider is not configured.
    assert j["router"]["rest_available"] is False
    rp = j["router"].get("rest_provider") or {}
    assert rp.get("configured") is False

    # We should at least produce a structured live_scan result.
    assert j["live_scan"]["status"]
    assert j["live_scan"]["reason"]

    after = set(data_dir.rglob("*") if data_dir.exists() else [])
    assert before == after
