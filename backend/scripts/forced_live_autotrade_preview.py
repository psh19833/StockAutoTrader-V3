"""forced_live_autotrade --preview (Phase1 E2E)

Goal:
- Holiday-safe end-to-end preview up to KIS order payload build
- Never submit real orders, never call KIS order API

Modes:
- --real: attempt LiveScannerAdapter (router-backed snapshots). Zero candidates is OK.
- --fixture: inject 1 candidate (default 005930) to force pipeline to reach payload.

Output:
- JSON report to stdout (single object)
"""

from __future__ import annotations

import os
import sys

# Ensure `backend/` is on sys.path when running as a script.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import argparse
import json
import tempfile
import uuid
from dataclasses import asdict
from typing import Any

from market_regime.regime_result import MarketRegimeResult
from market_regime.regime_state import MarketRegime
from market_regime.regime_score import MarketRegimeScore

from order.order_intent import OrderIntent
from order.order_types import OrderSide, OrderType
from order.live_order_gate import LiveOrderGate

from quant.scoring_calculator import evaluate_candidate
from risk.risk_context import RiskContext
from risk.risk_engine import evaluate_risk
from risk.risk_config import RiskLimits

from scanner.candidate import ScannerCandidate
from scanner.scanner_types import ScannerType

from session.session_state import TradingSessionState

from strategy.strategy_evaluator import evaluate_entry

from kis.order_api import build_cash_order_payload

from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache
from runtime.live_scanner import LiveScannerAdapter
from runtime.scheduler import SessionState
from runtime.live_real_audit import build_live_real_readonly_audit


def _safe_bool_env(key: str, default: bool = False) -> bool:
    v = str(os.getenv(key, ""))
    if not v:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _make_regime_result_for_preview() -> MarketRegimeResult:
    # We want pipeline connectivity (strategy/risk) even on holidays.
    # Therefore: allow_new_buy=True and regime=BULL (policy enabled).
    score = MarketRegimeScore(
        index_trend_score=20.0,
        market_breadth_score=15.0,
        market_momentum_score=12.0,
        volatility_risk_score=10.0,
        trading_value_score=8.0,
        sector_strength_score=8.0,
        foreign_institution_flow_score=4.0,
        market_risk_penalty=0.0,
    )
    return MarketRegimeResult(
        regime=MarketRegime.BULL,
        score=score,
        total_score=score.total_score,
        candidate_score_adjustment=0.0,
        allow_new_buy=True,
        min_candidate_score_required=50.0,
        reasons=("PREVIEW_OVERRIDE_ALLOW_NEW_BUY",),
        source_endpoints=("preview/fixture",),
        data_quality_warnings=(),
    )


def _candidate_from_live_row(row: dict[str, Any], scan_run_id: str = "") -> ScannerCandidate:
    # LiveScannerAdapter returns dict candidates with a nested metrics dict.
    metrics = dict(row.get("metrics") or {})
    # Ensure minimal fields exist.
    if "current_price" not in metrics:
        metrics["current_price"] = int(row.get("current_price", 0) or 0)
    if "trading_value" not in metrics:
        metrics["trading_value"] = int(row.get("trading_value", 0) or 0)
    if "spread_rate" not in metrics:
        metrics["spread_rate"] = float(row.get("spread_rate", 0.0) or 0.0)
    if "intraday_change_rate" not in metrics:
        metrics["intraday_change_rate"] = float(row.get("intraday_change_rate", 0.0) or 0.0)

    st = str(row.get("scanner_type", "LIQUIDITY_MOMENTUM") or "LIQUIDITY_MOMENTUM")
    try:
        scanner_type = ScannerType(st)
    except Exception:
        scanner_type = ScannerType.LIQUIDITY_MOMENTUM

    return ScannerCandidate(
        symbol=str(row.get("symbol", "") or ""),
        symbol_name=str(row.get("symbol_name") or row.get("name") or "") or None,
        market=str(row.get("market", "KOSPI") or "KOSPI"),
        product_type=str(row.get("product_type", "COMMON_STOCK") or "COMMON_STOCK"),
        scanner_type=scanner_type,
        metrics=metrics,
        source_endpoints=tuple(row.get("source_endpoints") or ()),
        scan_run_id=str(scan_run_id or row.get("scan_id", "") or ""),
        included=bool(row.get("included", True)),
        excluded_reason=row.get("excluded_reason"),
    )


def _fixture_candidate(symbol: str) -> ScannerCandidate:
    # Minimal-but-healthy metrics to produce PASS + high confidence.
    metrics = {
        "current_price": 70000,
        "intraday_high": 72000,
        "intraday_change_rate": 3.2,
        "trading_value": 120_000_000_000,  # 1200억
        "trading_value_rank": 10,
        "volume": 5_000_000,
        "volume_ratio_vs_recent_avg": 2.0,
        "spread_rate": 0.01,
        "execution_strength": 130.0,
        "volatility_ratio": 0.8,
        "vi_status": "INACTIVE",
        "is_management_issue": False,
        "is_investment_warning": False,
        "trading_halted": False,
        "pullback_from_high": 0.4,
        "rebound_volume_ratio": 1.2,
        "support_holding_score": 7.0,
        "prior_intraday_gain": 3.2,
    }
    return ScannerCandidate(
        symbol=symbol,
        symbol_name="FIXTURE",
        market="KOSPI",
        product_type="COMMON_STOCK",
        scanner_type=ScannerType.LIQUIDITY_MOMENTUM,
        metrics=metrics,
        source_endpoints=("fixture",),
        scan_run_id="fixture",
        included=True,
        excluded_reason=None,
    )


def _make_order_intent(*, signal, risk_decision, qty: int, price: int, order_type: OrderType) -> OrderIntent:
    side = OrderSide.BUY if str(signal.side).upper() == "BUY" else OrderSide.SELL
    estimated_amount = max(0, int(price) * int(qty))
    return OrderIntent(
        order_intent_id=f"oi_{uuid.uuid4().hex[:12]}",
        risk_decision_id=risk_decision.risk_decision_id,
        signal_id=signal.signal_id,
        correlation_id=signal.correlation_id,
        symbol=signal.symbol,
        side=side,
        order_type=order_type,
        quantity=int(qty),
        price=int(price),
        estimated_amount=int(estimated_amount),
        source_strategy=str(getattr(signal.strategy_type, "value", signal.strategy_type)),
        source_endpoints=tuple(signal.source_endpoints or ()),
        live_trading_enabled_snapshot=bool(_safe_bool_env("LIVE_TRADING_ENABLED", False)),
        approved_by_risk=bool(risk_decision.allowed),
    )


def _compute_soft_warnings(*, scan_status: str = "", scan_reason: str = "") -> list[str]:
    warnings: list[str] = []

    # These are explicitly treated as soft warnings for preview.
    if scan_status and scan_status != "READY":
        warnings.append(f"scanner_status:{scan_status}")
    if scan_reason:
        warnings.append(f"scanner_reason:{scan_reason}")

    # Market/session/holiday/readiness are not decided here; we keep as generic soft warnings.
    warnings.extend(
        [
            "session_state:UNKNOWN(soft)",
            "market_closed_or_holiday_possible(soft)",
            "readiness:NOT_READY(soft)",
            "snapshot_stale_or_mismatch_possible(soft)",
            "external_probe_disabled_possible(soft)",
            "telegram_target_valid_not_enforced_in_preview(soft)",
        ]
    )
    return warnings


def _hard_blocker_candidates_from_env() -> list[str]:
    cands: list[str] = []
    if not _safe_bool_env("LIVE_TRADING_ENABLED", False):
        cands.append("LIVE_TRADING_ENABLED=false")
    if not (str(os.getenv("SAT3_CONFIRM_LIVE_AUTO_TRADING", "")).strip() == "CONFIRM_LIVE_AUTO_TRADING"):
        cands.append("SAT3_CONFIRM_LIVE_AUTO_TRADING not confirmed")
    if not _safe_bool_env("SAT3_FORCED_LIVE_AUTOTRADE_ENABLED", False):
        cands.append("SAT3_FORCED_LIVE_AUTOTRADE_ENABLED=false")

    # Kill switch (candidate only)
    kill_path = str(os.getenv("SAT3_FORCED_LIVE_AUTOTRADE_KILL_SWITCH_PATH", "data/forced_live_kill_switch") or "")
    if kill_path:
        cands.append(f"kill_switch_path_candidate:{kill_path}")

    # Limit-related env (candidate only)
    max_krw = str(os.getenv("SAT3_FORCED_LIVE_AUTOTRADE_MAX_ORDER_KRW", "") or "").strip()
    if max_krw:
        cands.append(f"max_order_krw_env:{max_krw}")
    return cands


def _next_blocking_point_hint(report: dict[str, Any]) -> str | None:
    # Heuristic: what will likely block first in real live.
    if report["scanner"]["candidate_count"] == 0:
        return "scanner(no_candidates)"
    risk_allowed = report["risk"].get("allowed")
    if risk_allowed is False:
        return "risk_engine(rejected)"
    # live gate candidates
    for c in report.get("hard_blocker_candidates", []):
        if c.startswith("LIVE_TRADING_ENABLED=false"):
            return "live_order_gate(LIVE_TRADING_ENABLED=false)"
        if c.startswith("SAT3_CONFIRM_LIVE_AUTO_TRADING"):
            return "live_start_confirmation"
    return None


def run_preview(
    mode: str,
    symbol: str | None = None,
    rest_provider=None,
    real_universe_top_n: int | None = None,
    real_universe_params_json: str | None = None,
    universe_strict: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "mode": mode,
        "actual_order_submitted": False,
        "candidate_source": "scanner" if mode == "real" else "fixture",
        "scanner": {
            "candidate_count": 0,
            "selected_candidate": None,
            "empty_reason": None,
            # Observability: safe subset of candidates when available
            "candidates_preview": [],
            # Observability: always include a debug skeleton (never secrets)
            "debug": {
                "scan_status": None,
                "scan_reason": None,
                "scan_id": None,
                "stocks_built_count": 0,
                "stocks_built_count_source": "universe_symbol_count",
                "scanner_engine_summary": [],
            },
        },
        "strategy": {"decision": None, "reason": None},
        "risk": {"allowed": None, "blockers": [], "warnings": []},
        "order_intent": {"symbol": None, "side": None, "quantity": None, "price": None, "order_type": None},
        "kis_payload_preview": {},
        "soft_warnings": [],
        "hard_blocker_candidates": [],
        "next_blocking_point": None,
        "universe": {
            "source": "default_smoke",
            "top_n": None,
            "requested_top_n": None,
            "raw_row_count": None,
            "parsed_symbol_count": None,
            "used_symbol_count": None,
            "sample_count": 3,
            "limit_reason": "default_smoke_symbols",
            "count": 3,
            "symbols_sample": ["005930", "000660", "035720"],
            "fetch_error": None,
            "fallback_used": False,
            "strict": bool(universe_strict),
        },
        # fake/synthetic cleanup reporting (rule)
        "synthetic": {
            "file_created": False,
            "path": None,
            "auto_deleted": None,
            "delete_error": None,
        },
    }

    # Always include env-based hard blocker candidates (display only, never block preview).
    report["hard_blocker_candidates"] = _hard_blocker_candidates_from_env()

    scan_status = ""
    scan_reason = ""
    scan_id = ""

    candidate_obj: ScannerCandidate | None = None

    if mode == "real":
        audit = build_live_real_readonly_audit(
            rest_provider=rest_provider,
            real_universe_top_n=real_universe_top_n,
            real_universe_params_json=real_universe_params_json,
            universe_strict=bool(universe_strict),
            session=SessionState.REGULAR_MARKET.value,
        )
        report["rest_provider"] = rest_provider_meta
        report["scanner"]["candidate_count"] = len(audit.get("candidates") or [])
        report["scanner"]["selected_candidate"] = None
        if isinstance(audit.get("selected_candidate"), dict):
            sel = audit["selected_candidate"]
            report["scanner"]["selected_candidate"] = {
                "symbol": sel.get("symbol"),
                "scanner_type": sel.get("scanner_type"),
                "metrics_keys": sorted(list((sel.get("metrics") or {}).keys()))[:25],
            }
        report["scanner"]["candidates_preview"] = [
            {
                "symbol": c.get("symbol"),
                "scanner_type": c.get("scanner_type"),
                "score": c.get("score"),
                "current_price": (c.get("metrics") or {}).get("current_price"),
                "trading_value": (c.get("metrics") or {}).get("trading_value"),
                "trading_value_rank": c.get("trading_value_rank"),
                "intraday_change_rate": (c.get("metrics") or {}).get("intraday_change_rate"),
            }
            for c in (audit.get("candidates") or [])[:5]
            if isinstance(c, dict)
        ]
        report["scanner"]["debug"]["scan_status"] = audit.get("scanner_status")
        report["scanner"]["debug"]["scan_reason"] = audit.get("scanner_reason")
        report["scanner"]["debug"]["scan_id"] = audit.get("scan_id")
        report["strategy"]["decision"] = (audit.get("signals") or [None])[0]
        if audit.get("signals"):
            report["strategy"]["decision"] = audit["signals"][0]
            report["strategy"]["reason"] = None
        else:
            report["strategy"]["decision"] = None
            report["strategy"]["reason"] = "strategy(no_signal)"
        report["risk"]["allowed"] = bool((audit.get("risk_decisions") or [{}])[0].get("allowed", False)) if audit.get("risk_decisions") else None
        report["risk"]["blockers"] = []
        report["risk"]["warnings"] = []
        if audit.get("risk_decisions"):
            rd = audit["risk_decisions"][0]
            report["risk"]["allowed"] = bool(rd.get("allowed", False))
            if not rd.get("allowed", False):
                report["risk"]["blockers"] = [rd.get("reason_code") or rd.get("reason_text") or "RISK_REJECTED"]
        report["order_intent"] = {k: (audit.get("order_intents") or [{}])[0].get(k) for k in ("symbol", "side", "quantity", "price", "order_type")}
        report["actual_order_submitted"] = False
        report["next_blocking_point"] = audit.get("next_blocking_point") or _next_blocking_point_hint(report)
        report["kis_payload_preview"] = {}
        return report
    elif mode == "fixture":
        sym = symbol or "005930"
        candidate_obj = _fixture_candidate(sym)
        report["scanner"]["candidate_count"] = 1
        report["scanner"]["selected_candidate"] = {
            "symbol": candidate_obj.symbol,
            "scanner_type": candidate_obj.scanner_type.value,
            "metrics_keys": sorted(list(candidate_obj.metrics.keys()))[:25],
        }
    else:
        raise ValueError(f"Unknown mode: {mode}")

    report["soft_warnings"] = _compute_soft_warnings(scan_status=scan_status, scan_reason=scan_reason)

    if candidate_obj is None:
        report["next_blocking_point"] = _next_blocking_point_hint(report)
        return report

    # ── Strategy/Risk/Intent/Payload pipeline ──

    regime_result = _make_regime_result_for_preview()

    # Quant
    qscore = evaluate_candidate(candidate_obj, regime_result, config=None)

    # Strategy
    signal = evaluate_entry(qscore, regime_result)
    if signal is None:
        report["strategy"]["decision"] = None
        report["strategy"]["reason"] = "StrategySignal not created (policy/threshold/blocked)"
        report["risk"]["allowed"] = None
        report["next_blocking_point"] = "strategy(no_signal)"
        return report

    report["strategy"]["decision"] = {
        "symbol": signal.symbol,
        "side": signal.side,
        "strategy_type": getattr(signal.strategy_type, "value", str(signal.strategy_type)),
        "confidence": signal.confidence,
        "market_regime": signal.market_regime,
        "scanner_type": signal.scanner_type,
    }

    # Risk
    # For preview connectivity we use REGULAR_MARKET + allow_new_buy=True.
    # Any mismatch with real session/readiness is recorded as soft warnings.
    ctx = RiskContext(
        market_regime_result=regime_result,
        session_state=TradingSessionState.REGULAR_MARKET,
        emergency_stop=False,
        live_trading_enabled=_safe_bool_env("LIVE_TRADING_ENABLED", False),
        current_positions=frozenset(),
        pending_orders=frozenset(),
        today_realized_pnl=0,
        daily_loss_limit=1_000_000,
        data_quality_warnings=(),
    )

    # Requested amount estimation
    current_price = int(candidate_obj.metrics.get("current_price", 0) or 0)
    qty = 1
    est_amount = max(0, current_price * qty)

    rd = evaluate_risk(
        signal=signal,
        context=ctx,
        requested_amount=est_amount,
        limits=RiskLimits(),
    )

    report["risk"]["allowed"] = bool(rd.allowed)
    report["risk"]["blockers"] = list(rd.failed_items or ())
    report["risk"]["warnings"] = list(ctx.data_quality_warnings or ())

    # Order intent (even if risk rejected: we still build an intent preview skeleton)
    order_type = OrderType.MARKET if current_price <= 0 else OrderType.MARKET
    intent = _make_order_intent(
        signal=signal,
        risk_decision=rd,
        qty=qty,
        price=current_price,
        order_type=order_type,
    )

    report["order_intent"] = {
        "symbol": intent.symbol,
        "side": intent.side.value,
        "quantity": intent.quantity,
        "price": intent.price,
        "order_type": intent.order_type.value,
    }

    # LiveOrderGate (display-only)
    gate = LiveOrderGate(
        live_trading_enabled=_safe_bool_env("LIVE_TRADING_ENABLED", False),
        emergency_stop=False,
        session_state=TradingSessionState.REGULAR_MARKET,
        allow_new_buy=True,
        max_order_amount=int(os.getenv("SAT3_FORCED_LIVE_AUTOTRADE_MAX_ORDER_KRW", "10000000") or "10000000"),
    )
    gate_result = gate.check(rd, estimated_amount=intent.estimated_amount)
    if not gate_result.allowed:
        report["hard_blocker_candidates"].append(f"live_order_gate:{gate_result.message}")

    # KIS payload preview (NO submit)
    # Account fields intentionally blank for preview.
    payload = build_cash_order_payload(
        symbol=intent.symbol,
        side=intent.side.value,
        qty=intent.quantity,
        price=intent.price,
        order_type=intent.order_type.value,
        account_no="",
        account_product_code="01",
    )
    report["kis_payload_preview"] = payload

    report["order_type_mapping_note"] = {
        "order_intent_order_type": intent.order_type.value,
        "kis_ord_dvsn": payload.get("ORD_DVSN"),
        "kis_ord_unpr": payload.get("ORD_UNPR"),
        "policy": "LIMIT->ORD_DVSN=00, ORD_UNPR=price; MARKET->ORD_DVSN=01, ORD_UNPR=0",
    }

    # Optional synthetic dump for rehearsal/debug (tempfile + auto-delete)
    _maybe_dump_synthetic_candidate_json(
        report=report,
        candidate_obj=candidate_obj,
        enabled=_safe_bool_env("SAT3_PREVIEW_DUMP_SYNTHETIC", False),
    )

    report["next_blocking_point"] = _next_blocking_point_hint(report)
    return report


def _maybe_dump_synthetic_candidate_json(report: dict[str, Any], candidate_obj: ScannerCandidate, enabled: bool) -> None:
    """Optionally dump synthetic candidate JSON to a temp file and delete it.

    Cleanup rules:
    - Never writes under data/
    - Uses tempfile
    - Attempts deletion before returning
    - Records deletion result in report["synthetic"]
    """
    if not enabled:
        return

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".synthetic.candidate.json",
        prefix="sat3_rehearsal_",
        delete=False,
    )
    path = tmp.name
    try:
        def _default(o):
            # Ensure rehearsal dump never fails on datetimes/enums.
            return str(o)

        json.dump(asdict(candidate_obj), tmp, ensure_ascii=False, indent=2, default=_default)
        tmp.flush()
        tmp.close()
        report["synthetic"]["file_created"] = True
        report["synthetic"]["path"] = path
    except Exception as e:
        report["synthetic"]["file_created"] = False
        report["synthetic"]["path"] = path
        report["synthetic"]["auto_deleted"] = False
        report["synthetic"]["delete_error"] = f"write_failed:{type(e).__name__}:{e}"
        return
    finally:
        try:
            import os as _os

            if _os.path.exists(path):
                _os.remove(path)
            report["synthetic"]["auto_deleted"] = True
        except Exception as e2:  # pragma: no cover
            report["synthetic"]["auto_deleted"] = False
            report["synthetic"]["delete_error"] = f"delete_failed:{type(e2).__name__}:{e2}"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--real", action="store_true", help="attempt real scanner path")
    g.add_argument("--fixture", action="store_true", help="inject fixture candidate")
    p.add_argument("--symbol", default=None, help="fixture symbol (e.g. 005930)")
    p.add_argument(
        "--use-real-rest",
        action="store_true",
        help="(read-only) try to inject KIS REST provider for --real scanner",
    )
    p.add_argument(
        "--real-universe-top-n",
        type=int,
        default=None,
        help="(read-only) for --real: expand universe using KIS volume-top ranking (best-effort).",
    )
    p.add_argument(
        "--real-universe-params-json",
        default=None,
        help="JSON string for KIS volume-top params (optional; avoid printing secrets).",
    )
    p.add_argument(
        "--universe-strict",
        action="store_true",
        help="If universe expansion is requested and fetch fails, do NOT fall back to default symbols.",
    )
    args = p.parse_args(argv)

    mode = "real" if args.real else "fixture"

    rest_provider = None
    rest_provider_meta = {"configured": False, "reason": "disabled"}
    if args.use_real_rest and mode == "real":
        from runtime.rest_provider_factory import maybe_create_kis_rest_provider

        rest_provider, rest_provider_meta = maybe_create_kis_rest_provider()

    report = run_preview(
        mode=mode,
        symbol=args.symbol,
        rest_provider=rest_provider,
        real_universe_top_n=args.real_universe_top_n,
        real_universe_params_json=args.real_universe_params_json,
        universe_strict=bool(args.universe_strict),
    )
    report["rest_provider"] = rest_provider_meta
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
