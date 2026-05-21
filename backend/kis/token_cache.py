"""Persistent KIS token cache (cache-first)

Goals (SAT3 policy):
- Allow storing access_token on local disk OUTSIDE the repo (never in logs/data/repo)
- Enforce file permissions (dir 700, file 600)
- Support cache-first reuse until expiry
- Record minimal tokenP attempt metadata to enforce "KST date 1-day" guard
- NEVER print token value; callers must not log it.
"""

from __future__ import annotations

import json
import os
import stat
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    return datetime.now(KST)


def _to_epoch(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def app_key_fingerprint(app_key: str) -> str:
    """Non-reversible fingerprint suitable for cache metadata."""
    if not app_key:
        return ""
    return _sha256_hex(app_key)[:12]


def base_url_hash(base_url: str) -> str:
    if not base_url:
        return ""
    return _sha256_hex(base_url)[:12]


def default_cache_path() -> Path:
    env = os.getenv("SAT3_KIS_TOKEN_CACHE_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".sat3" / "kis_token_cache.json"


def ensure_secure_path(path: Path) -> None:
    path = path.expanduser()
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(parent, 0o700)
    except Exception:
        # best-effort; still continue
        pass

    if path.exists():
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass


def _is_mode_ok(mode: int, desired: int) -> bool:
    return stat.S_IMODE(mode) == desired


def check_permissions(path: Path) -> dict[str, Any]:
    path = path.expanduser()
    out: dict[str, Any] = {
        "dir_exists": path.parent.exists(),
        "file_exists": path.exists(),
        "dir_mode_ok": None,
        "file_mode_ok": None,
    }
    try:
        st_dir = path.parent.stat()
        out["dir_mode_ok"] = _is_mode_ok(st_dir.st_mode, 0o700)
    except Exception:
        out["dir_mode_ok"] = None
    if path.exists():
        try:
            st = path.stat()
            out["file_mode_ok"] = _is_mode_ok(st.st_mode, 0o600)
        except Exception:
            out["file_mode_ok"] = None
    return out


@dataclass
class TokenCacheRecord:
    access_token: str = ""
    token_type: str = "Bearer"
    issued_at_epoch: int = 0
    expires_at_epoch: int = 0
    issued_at_kst: str = ""
    expires_at_kst: str = ""
    source: str = ""
    base_url_hash: str = ""
    app_key_fingerprint: str = ""

    last_tokenp_attempt_at_kst: str = ""
    last_tokenp_attempt_date_kst: str = ""  # YYYY-MM-DD
    last_tokenp_success_at_kst: str = ""
    last_tokenp_failure_code: str = ""
    last_tokenp_failure_message_redacted: str = ""


class TokenCache:
    def __init__(self, path: Path | None = None):
        self.path = (path or default_cache_path()).expanduser()

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> TokenCacheRecord | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            data = {}
            for k in TokenCacheRecord.__annotations__.keys():
                v = raw.get(k)
                if v is None:
                    # fall back to dataclass defaults
                    continue
                data[k] = v
            rec = TokenCacheRecord(**data)
            return rec
        except Exception:
            return None

    def save(self, rec: TokenCacheRecord) -> None:
        ensure_secure_path(self.path)
        data = {k: getattr(rec, k) for k in TokenCacheRecord.__annotations__.keys()}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except Exception:
            pass
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except Exception:
            pass

    def record_tokenp_attempt(
        self,
        *,
        base_url: str,
        app_key: str,
        success: bool,
        issued_at_utc: datetime | None = None,
        expires_in: int | None = None,
        token_type: str | None = None,
        access_token: str | None = None,
        failure_code: str = "",
        failure_message_redacted: str = "",
        source: str = "KIS_TOKENP",
    ) -> TokenCacheRecord:
        now_kst = _now_kst()
        date_kst = now_kst.strftime("%Y-%m-%d")
        rec = self.load() or TokenCacheRecord()
        rec.last_tokenp_attempt_at_kst = now_kst.isoformat()
        rec.last_tokenp_attempt_date_kst = date_kst
        rec.base_url_hash = base_url_hash(base_url)
        rec.app_key_fingerprint = app_key_fingerprint(app_key)

        if success and issued_at_utc and expires_in is not None and access_token and token_type:
            issued_kst = issued_at_utc.astimezone(KST)
            expires_utc = issued_at_utc + timedelta(seconds=int(expires_in))
            expires_kst = expires_utc.astimezone(KST)

            rec.access_token = access_token
            rec.token_type = token_type
            rec.issued_at_epoch = _to_epoch(issued_at_utc)
            rec.expires_at_epoch = _to_epoch(expires_utc)
            rec.issued_at_kst = issued_kst.isoformat()
            rec.expires_at_kst = expires_kst.isoformat()
            rec.source = source

            rec.last_tokenp_success_at_kst = now_kst.isoformat()
            rec.last_tokenp_failure_code = ""
            rec.last_tokenp_failure_message_redacted = ""
        else:
            # failure metadata only; keep existing valid token if present
            rec.last_tokenp_failure_code = failure_code or rec.last_tokenp_failure_code
            rec.last_tokenp_failure_message_redacted = failure_message_redacted or rec.last_tokenp_failure_message_redacted

        self.save(rec)
        return rec

    def token_present(self, rec: TokenCacheRecord | None) -> bool:
        return bool(rec and rec.access_token and rec.token_type)

    def is_expired(self, rec: TokenCacheRecord | None) -> bool | None:
        if not rec or not rec.expires_at_epoch:
            return None
        return int(datetime.now(timezone.utc).timestamp()) >= int(rec.expires_at_epoch)

    def kst_attempted_today(self, rec: TokenCacheRecord | None) -> bool:
        if not rec or not rec.last_tokenp_attempt_date_kst:
            return False
        return rec.last_tokenp_attempt_date_kst == _now_kst().strftime("%Y-%m-%d")
