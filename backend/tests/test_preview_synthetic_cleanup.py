from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "backend" / "scripts" / "forced_live_autotrade_preview.py"


def _run(args: list[str], env: dict[str, str] | None = None) -> dict:
    cmd = [str(REPO_ROOT / ".venv" / "bin" / "python"), str(SCRIPT)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
    return json.loads(p.stdout)


def test_synthetic_dump_uses_temp_and_auto_deletes(tmp_path: Path) -> None:
    # Baseline data/ should not gain synthetic files.
    data_dir = REPO_ROOT / "data"
    before = set(data_dir.rglob("*")) if data_dir.exists() else set()

    env = os.environ.copy()
    env["SAT3_PREVIEW_DUMP_SYNTHETIC"] = "1"

    r = _run(["--fixture", "--symbol", "005930"], env=env)

    syn = r.get("synthetic") or {}
    assert syn.get("file_created") is True
    path = syn.get("path")
    assert path

    # Must not be under repo data/
    assert str(data_dir) not in str(path)

    # Must be auto-deleted
    assert syn.get("auto_deleted") is True
    assert not Path(path).exists()

    after = set(data_dir.rglob("*")) if data_dir.exists() else set()
    assert before == after


def test_real_mode_does_not_auto_read_synthetic(tmp_path: Path) -> None:
    # Create a synthetic-looking candidate file; real mode should ignore it.
    synthetic = tmp_path / "synthetic_candidate.json"
    synthetic.write_text("{}", encoding="utf-8")

    # No CLI arg exists to pass candidate json to real mode; ensure run still works.
    r = _run(["--real"], env=os.environ.copy())
    assert r.get("mode") == "real"
    assert r.get("candidate_source") == "scanner"
    # real-mode should not report any synthetic path
    syn = r.get("synthetic") or {}
    assert syn.get("file_created") is False
