from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UniverseFetchResult:
    symbols: list[str]
    source: str
    top_n: int | None = None
    # Observability-only fields (read-only)
    raw_row_count: int | None = None
    parsed_symbol_count: int | None = None
    used_symbol_count: int | None = None
    error_type: str | None = None
    error_reason: str | None = None
    http_status: int | None = None
    rt_cd: str | None = None
    msg_cd: str | None = None
    msg1: str | None = None
    fallback_used: bool = False


def _normalize_symbols(symbols: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        s2 = str(s).strip()
        if not s2:
            continue
        if s2 in seen:
            continue
        seen.add(s2)
        out.append(s2)
    return out


def parse_symbols_from_rank_payload(payload: Any) -> list[str]:
    """Best-effort parse of symbol list from KIS ranking payload.

    We deliberately avoid hardcoding a single key name; different endpoints/versions
    may return different key names.

    Acceptable shapes:
      - dict with output/output1/output2 as list[dict]
      - list[dict]

    Candidate symbol keys:
      - mksc_shrn_iscd
      - stck_shrn_iscd
      - iscd
      - code
      - symbol
    """
    candidates = ("mksc_shrn_iscd", "stck_shrn_iscd", "iscd", "code", "symbol")

    items: list[dict] = []
    if isinstance(payload, dict):
        for k in ("output", "output1", "output2", "data"):
            v = payload.get(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items = v
                break
        # Some wrappers may pass {raw: {...}}
        if not items and "raw" in payload and isinstance(payload["raw"], dict):
            return parse_symbols_from_rank_payload(payload["raw"])
    elif isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            items = payload

    symbols: list[str] = []
    for row in items:
        for key in candidates:
            if key in row and row[key]:
                symbols.append(str(row[key]))
                break

    return _normalize_symbols(symbols)


def fetch_universe_from_kis_volume_top(
    facade,
    top_n: int,
    params: dict[str, Any] | None = None,
) -> UniverseFetchResult:
    """Fetch top-N symbols using KIS read-only volume-top endpoint (best-effort).

    Important: This function MUST stay read-only. It only calls facade.get_volume_top.
    """
    try:
        resp = facade.get_volume_top(params=params or {})
        if not resp or not resp.get("data_available"):
            return UniverseFetchResult(
                symbols=[],
                source="kis_volume_top",
                top_n=top_n,
                error_type=str(resp.get("error_type") if isinstance(resp, dict) else None) or "DataUnavailable",
                error_reason=(
                    str(resp.get("reason_code") if isinstance(resp, dict) else None)
                    or str(resp.get("reason_text") if isinstance(resp, dict) else None)
                    or "volume_top_unavailable"
                ),
                http_status=resp.get("http_status") if isinstance(resp, dict) else None,
                rt_cd=str(resp.get("rt_cd") if isinstance(resp, dict) else None) if isinstance(resp, dict) else None,
                msg_cd=str(resp.get("msg_cd") if isinstance(resp, dict) else None) if isinstance(resp, dict) else None,
                msg1=str(resp.get("msg1") if isinstance(resp, dict) else None) if isinstance(resp, dict) else None,
            )
        raw = resp.get("raw") if isinstance(resp, dict) else None

        raw_rows = None
        if isinstance(raw, dict):
            for k in ("output", "output1", "output2", "data"):
                v = raw.get(k)
                if isinstance(v, list):
                    raw_rows = len(v)
                    break

        parsed = parse_symbols_from_rank_payload(raw)
        used = parsed[: max(0, int(top_n))]
        return UniverseFetchResult(
            symbols=used,
            source="kis_volume_top",
            top_n=top_n,
            raw_row_count=raw_rows,
            parsed_symbol_count=len(parsed),
            used_symbol_count=len(used),
            http_status=resp.get("http_status") if isinstance(resp, dict) else None,
            rt_cd=str(resp.get("rt_cd") if isinstance(resp, dict) else None) if isinstance(resp, dict) else None,
            msg_cd=str(resp.get("msg_cd") if isinstance(resp, dict) else None) if isinstance(resp, dict) else None,
            msg1=str(resp.get("msg1") if isinstance(resp, dict) else None) if isinstance(resp, dict) else None,
        )
    except Exception as e:
        return UniverseFetchResult(
            symbols=[],
            source="kis_volume_top",
            top_n=top_n,
            error_type=type(e).__name__,
            error_reason="volume_top_exception",
        )
