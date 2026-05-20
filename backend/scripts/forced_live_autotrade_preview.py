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
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "mode": mode,
        "actual_order_submitted": False,
        "candidate_source": "scanner" if mode == "real" else "fixture",
        "scanner": {
            "candidate_count": 0,
            "selected_candidate": None,
            "empty_reason": None,
        },
        "strategy": {"decision": None, "reason": None},
        "risk": {"allowed": None, "blockers": [], "warnings": []},
        "order_intent": {"symbol": None, "side": None, "quantity": None, "price": None, "order_type": None},
        "kis_payload_preview": {},
        "soft_warnings": [],
        "hard_blocker_candidates": [],
        "next_blocking_point": None,
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
        router = MarketDataRouter(MarketCache(), rest_provider=rest_provider)
        scanner = LiveScannerAdapter(router)
        # We force the session argument to REGULAR_MARKET to maximize scan attempt.
        scan = scanner.run_live_scan(session=SessionState.REGULAR_MARKET.value)
        scan_status = scan.status
        scan_reason = scan.reason
        scan_id = scan.scan_id
        candidates = list(scan.candidates or [])
        report["scanner"]["candidate_count"] = len(candidates)
        if not candidates:
            # NOTE: LiveScannerAdapter returns LIVE_SCANNER_OK even if *all* candidates were excluded.
            # We record a more informative empty_reason and include debug details (no secrets).
            report["scanner"]["empty_reason"] = scan_reason or scan_status or "NO_CANDIDATES"

            debug: dict[str, Any] = {
                "scan_status": scan_status,
                "scan_reason": scan_reason,
                "stocks_built_count": 0,
                "per_symbol": [],
                "scanner_engine_summary": [],
            }

            # For DATA_UNAVAILABLE debugging (scanner.filters.check_common_filters)
            required_common_fields = [
                "current_price",
                "trading_value",
                "volume",
                "spread_rate",
                "is_trading_halted",
                "is_management_issue",
                "is_investment_warning",
            ]

            symbols = ["005930", "000660", "035720"]
            stocks: list[dict[str, Any]] = []
            for s in symbols:
                row = scanner._build_stock_metrics(s)  # preview diagnostic-only
                if row is None:
                    debug["per_symbol"].append({"symbol": s, "metrics_built": False})
                    continue
                stocks.append(row)

                missing_fields = [k for k in required_common_fields if k not in row or row.get(k) is None]
                invalid_fields: list[str] = []
                for k in ("current_price", "trading_value", "volume", "spread_rate"):
                    v = row.get(k)
                    if v in (None, "", "-", "N/A", "nan", "NaN", "null"):
                        invalid_fields.append(f"{k}={v}")

                debug["per_symbol"].append(
                    {
                        "symbol": s,
                        "metrics_built": True,
                        "current_price": row.get("current_price"),
                        "volume": row.get("volume"),
                        "trading_value": row.get("trading_value"),
                        "spread_rate": row.get("spread_rate"),
                        "intraday_change_rate": row.get("intraday_change_rate"),
                        "price_source": "router.trade_tick_snapshot.trade_price",
                        "volume_source": "router.trade_tick_snapshot.accumulated_volume_or_trade_volume",
                        "trading_value_source": "router.trade_tick_snapshot.accumulated_trading_value_or_fallback",
                        "raw_volume_candidate": row.get("volume"),
                        "raw_trading_value_candidate": row.get("trading_value"),
                        "trading_value_filter_min": 500_000_000,
                        "trading_value_pass": bool((row.get("trading_value") or 0) >= 500_000_000),
                        "price_filter_max": 1_000_000,
                        "price_pass": bool((row.get("current_price") or 0) <= 1_000_000),
                        "missing_required_common_fields": missing_fields,
                        "zero_or_invalid_common_fields": invalid_fields,
                    }
                )
            debug["stocks_built_count"] = len(stocks)

            if stocks:
                try:
                    from scanner.scanner_engine import run_all_scanners

                    results = run_all_scanners(
                        stocks=stocks,
                        market_regime="NEUTRAL",
                        scan_run_id=scan_id,
                    )
                    for r in results:
                        excluded_reasons: dict[str, int] = {}
                        included_count = 0
                        excluded_count = 0
                        for c in getattr(r, "candidates", ()) or ():
                            if getattr(c, "included", False):
                                included_count += 1
                            else:
                                excluded_count += 1
                                reason = str(getattr(c, "excluded_reason", "") or "")
                                excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
                        top_reasons = sorted(
                            excluded_reasons.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )[:5]
                        debug["scanner_engine_summary"].append(
                            {
                                "scanner_type": str(getattr(r, "scanner_type", "")),
                                "collected_count": int(getattr(r, "collected_count", 0) or 0),
                                "included_count": included_count,
                                "excluded_count": excluded_count,
                                "top_excluded_reasons": top_reasons,
                            }
                        )

                    if scan_reason == "LIVE_SCANNER_OK":
                        report["scanner"]["empty_reason"] = "LIVE_SCANNER_OK_BUT_NO_CANDIDATES"
                except Exception as e:
                    debug["scanner_engine_summary"].append(
                        {"error": f"scanner_summary_failed:{type(e).__name__}"}
                    )

            report["scanner"]["debug"] = debug
        else:
            sel = candidates[0]
            report["scanner"]["selected_candidate"] = {
                "symbol": sel.get("symbol"),
                "scanner_type": sel.get("scanner_type"),
                "metrics_keys": sorted(list((sel.get("metrics") or {}).keys()))[:25],
            }
            candidate_obj = _candidate_from_live_row(sel, scan_run_id=scan_id)

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
    args = p.parse_args(argv)

    mode = "real" if args.real else "fixture"

    rest_provider = None
    rest_provider_meta = {"configured": False, "reason": "disabled"}
    if args.use_real_rest and mode == "real":
        from runtime.rest_provider_factory import maybe_create_kis_rest_provider

        rest_provider, rest_provider_meta = maybe_create_kis_rest_provider()

    report = run_preview(mode=mode, symbol=args.symbol, rest_provider=rest_provider)
    report["rest_provider"] = rest_provider_meta
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
