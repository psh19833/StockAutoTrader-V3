from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
import json
import os
import uuid

from market_regime.regime_result import MarketRegimeResult
from market_regime.regime_state import MarketRegime
from market_regime.regime_score import MarketRegimeScore
from quant.scoring_calculator import evaluate_candidate
from risk.risk_config import RiskLimits
from risk.risk_context import RiskContext
from risk.risk_engine import evaluate_risk
from scanner.candidate import ScannerCandidate
from scanner.scanner_types import ScannerType
from strategy.strategy_evaluator import evaluate_entry
from order.order_intent import OrderIntent
from order.order_types import OrderSide, OrderType
from runtime.data_router import MarketDataRouter
from runtime.live_scanner import LiveScannerAdapter
from runtime.market_cache import MarketCache
from runtime.scheduler import SessionState
from runtime.universe_source import fetch_universe_from_kis_volume_top
from session.session_state import TradingSessionState


DEFAULT_REAL_UNIVERSE_TOP_N = 20


def _safe_bool_env(key: str, default: bool = False) -> bool:
    v = str(os.getenv(key, "") or "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "y", "on"}


def _make_regime_result_for_preview() -> MarketRegimeResult:
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
    metrics = dict(row.get("metrics") or {})
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


def _order_intent_dict(*, signal: Any, risk_decision: Any, qty: int, price: int, order_type: OrderType) -> dict[str, Any]:
    side = OrderSide.BUY if str(getattr(signal, "side", "")).upper() == "BUY" else OrderSide.SELL
    estimated_amount = max(0, int(price) * int(qty))
    intent = OrderIntent(
        order_intent_id=f"oi_{uuid.uuid4().hex[:12]}",
        risk_decision_id=str(getattr(risk_decision, "risk_decision_id", "")),
        signal_id=str(getattr(signal, "signal_id", "")),
        correlation_id=str(getattr(signal, "correlation_id", "")),
        symbol=str(getattr(signal, "symbol", "")),
        side=side,
        order_type=order_type,
        quantity=int(qty),
        price=int(price),
        estimated_amount=int(estimated_amount),
        source_strategy=str(getattr(signal, "strategy_type", "")),
        source_endpoints=tuple(getattr(signal, "source_endpoints", ()) or ()),
        live_trading_enabled_snapshot=bool(_safe_bool_env("LIVE_TRADING_ENABLED", False)),
        approved_by_risk=bool(getattr(risk_decision, "allowed", False)),
    )
    return {
        "order_intent_id": intent.order_intent_id,
        "risk_decision_id": intent.risk_decision_id,
        "signal_id": intent.signal_id,
        "correlation_id": intent.correlation_id,
        "symbol": intent.symbol,
        "side": intent.side.value,
        "order_type": intent.order_type.value,
        "quantity": intent.quantity,
        "price": intent.price,
        "estimated_amount": intent.estimated_amount,
        "source_strategy": intent.source_strategy,
        "source_endpoints": list(intent.source_endpoints or ()),
        "live_trading_enabled_snapshot": intent.live_trading_enabled_snapshot,
        "approved_by_risk": intent.approved_by_risk,
        "submitted": False,
        "blocked_reason": "AUDIT_ONLY_NO_SUBMIT",
        "mode": "LIVE",
        "synthetic": False,
        "source": "LIVE_REAL_READONLY_AUDIT",
    }


def _to_score_dict(qscore: Any, candidate: ScannerCandidate) -> dict[str, Any]:
    return {
        "symbol": candidate.symbol,
        "scanner_type": getattr(candidate.scanner_type, "value", str(candidate.scanner_type)),
        "decision": str(getattr(qscore, "decision", "")),
        "final_score": float(getattr(qscore, "final_score", 0.0) or 0.0),
        "liquidity_score": float(getattr(qscore, "liquidity_score", 0.0) or 0.0),
        "momentum_score": float(getattr(qscore, "momentum_score", 0.0) or 0.0),
        "mode": "LIVE",
        "synthetic": False,
        "source": "LIVE_REAL_READONLY_AUDIT",
    }


def _to_signal_dict(signal: Any, candidate: ScannerCandidate, qscore: Any) -> dict[str, Any]:
    return {
        "signal_id": str(getattr(signal, "signal_id", f"sig_{candidate.symbol}")),
        "correlation_id": str(getattr(signal, "correlation_id", f"corr_{candidate.symbol}")),
        "symbol": candidate.symbol,
        "side": str(getattr(signal, "side", "")),
        "strategy_type": str(getattr(signal, "strategy_type", getattr(candidate.scanner_type, "value", candidate.scanner_type))),
        "confidence": float(getattr(signal, "confidence", getattr(qscore, "final_score", 0.0)) or 0.0),
        "market_regime": str(getattr(signal, "market_regime", "UNKNOWN")),
        "scanner_type": getattr(candidate.scanner_type, "value", str(candidate.scanner_type)),
        "source_endpoints": list(getattr(signal, "source_endpoints", ()) or ()),
        "mode": "LIVE",
        "synthetic": False,
        "source": "LIVE_REAL_READONLY_AUDIT",
    }


def _to_risk_dict(risk_decision: Any, signal: Any, candidate: ScannerCandidate) -> dict[str, Any]:
    return {
        "risk_decision_id": str(getattr(risk_decision, "risk_decision_id", f"risk_{candidate.symbol}")),
        "signal_id": str(getattr(signal, "signal_id", f"sig_{candidate.symbol}")),
        "correlation_id": str(getattr(signal, "correlation_id", f"corr_{candidate.symbol}")),
        "symbol": candidate.symbol,
        "side": str(getattr(signal, "side", "")),
        "allowed": bool(getattr(risk_decision, "allowed", False)),
        "reason_code": str(getattr(risk_decision, "reason_code", "")),
        "reason_text": str(getattr(risk_decision, "reason_text", "")),
        "mode": "LIVE",
        "synthetic": False,
        "source": "LIVE_REAL_READONLY_AUDIT",
    }


def _build_universe_symbols(*, rest_provider: Any | None, real_universe_top_n: int | None, real_universe_params_json: str | None) -> tuple[list[str] | None, dict[str, Any]]:
    universe = {
        "source": "live_scan_default",
        "top_n": None,
        "requested_top_n": None,
        "raw_row_count": None,
        "parsed_symbol_count": None,
        "used_symbol_count": None,
        "sample_count": 0,
        "limit_reason": "live_scan_default",
        "count": None,
        "symbols_sample": [],
        "fetch_error": None,
        "fallback_used": False,
        "strict": False,
    }

    top_n = real_universe_top_n
    if top_n is None and rest_provider is not None:
        env_top = str(os.getenv("SAT3_LIVE_REAL_UNIVERSE_TOP_N", "") or "").strip()
        if env_top:
            try:
                top_n = int(env_top)
            except Exception:
                top_n = DEFAULT_REAL_UNIVERSE_TOP_N
        else:
            top_n = DEFAULT_REAL_UNIVERSE_TOP_N

    if top_n is None:
        universe["count"] = 0
        return None, universe

    universe["top_n"] = int(top_n)
    universe["requested_top_n"] = int(top_n)
    universe["source"] = "kis_volume_top"
    universe["limit_reason"] = "requested_kis_volume_top"
    params = None
    if real_universe_params_json:
        try:
            params = json.loads(real_universe_params_json)
        except Exception:
            universe["fetch_error"] = "params_json_parse_failed"
            params = None

    if rest_provider is None:
        universe["fetch_error"] = universe["fetch_error"] or "rest_provider_disabled"
        universe["count"] = 0
        return [], universe

    facade = getattr(rest_provider, "_facade", None)
    if facade is None:
        universe["fetch_error"] = universe["fetch_error"] or "facade_unavailable"
        universe["count"] = 0
        return [], universe

    try:
        res = fetch_universe_from_kis_volume_top(facade, top_n=int(top_n), params=params)
        if res.symbols:
            universe["raw_row_count"] = getattr(res, "raw_row_count", None)
            universe["parsed_symbol_count"] = getattr(res, "parsed_symbol_count", None)
            universe["used_symbol_count"] = getattr(res, "used_symbol_count", None)
            universe["count"] = len(res.symbols)
            universe["symbols_sample"] = list(res.symbols[: min(10, len(res.symbols))])
            universe["sample_count"] = len(universe["symbols_sample"])
            universe["limit_reason"] = "used_symbols_from_kis_volume_top"
            return list(res.symbols), universe
        universe["fetch_error"] = universe["fetch_error"] or (res.error_type or res.error_reason or "universe_empty")
        universe["count"] = 0
        return [], universe
    except Exception as e:
        universe["fetch_error"] = f"universe_fetch_failed:{type(e).__name__}"
        universe["count"] = 0
        return [], universe


def build_live_real_readonly_audit(
    *,
    rest_provider: Any | None = None,
    real_universe_top_n: int | None = None,
    real_universe_params_json: str | None = None,
    universe_strict: bool = False,
    session: str = SessionState.REGULAR_MARKET.value,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    scanner = LiveScannerAdapter(MarketDataRouter(MarketCache(), rest_provider=rest_provider))

    audit: dict[str, Any] = {
        "source": "LIVE_REAL_READONLY_AUDIT",
        "synthetic": False,
        "mode": "LIVE",
        "generated_at": generated_at,
        "scan_id": "",
        "scanner_status": "",
        "scanner_reason": "",
        "universe": {},
        "candidates": [],
        "scores": [],
        "signals": [],
        "risk_decisions": [],
        "order_intents": [],
        "selected_candidate": None,
        "actual_order_submitted": False,
    }

    symbols, universe = _build_universe_symbols(
        rest_provider=rest_provider,
        real_universe_top_n=real_universe_top_n,
        real_universe_params_json=real_universe_params_json,
    )
    audit["universe"] = universe
    if universe.get("fetch_error") and universe_strict:
        audit["scanner_status"] = "BLOCKED_UNIVERSE_FETCH_ERROR"
        audit["scanner_reason"] = str(universe.get("fetch_error") or "UNIVERSE_FETCH_ERROR")
        audit["next_blocking_point"] = "universe(fetch_error)"
        return audit
    if symbols is None:
        audit["scanner_status"] = "BLOCKED_UNIVERSE_UNAVAILABLE"
        audit["scanner_reason"] = "REST_PROVIDER_UNAVAILABLE"
        audit["next_blocking_point"] = "universe(rest_provider_unavailable)"
        return audit

    scan = scanner.run_live_scan(session=session, symbols=symbols)
    audit["scan_id"] = scan.scan_id
    audit["scanner_status"] = scan.status
    audit["scanner_reason"] = scan.reason
    audit["candidates"] = list(scan.candidates or [])

    candidates = list(scan.candidates or [])
    if not candidates:
        audit["next_blocking_point"] = "scanner(no_candidates)"
        return audit

    selected = candidates[0]
    audit["selected_candidate"] = dict(selected)

    candidate_obj = _candidate_from_live_row(selected, scan_run_id=scan.scan_id)
    regime_result = _make_regime_result_for_preview()
    qscore = evaluate_candidate(candidate_obj, regime_result, config=None)
    audit["scores"] = [_to_score_dict(qscore, candidate_obj)]

    signal = evaluate_entry(qscore, regime_result)
    if signal is None:
        audit["next_blocking_point"] = "strategy(no_signal)"
        return audit

    audit["signals"] = [_to_signal_dict(signal, candidate_obj, qscore)]

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

    current_price = int(candidate_obj.metrics.get("current_price", 0) or 0)
    qty = 1
    est_amount = max(0, current_price * qty)
    rd = evaluate_risk(
        signal=signal,
        context=ctx,
        requested_amount=est_amount,
        limits=RiskLimits(),
    )
    audit["risk_decisions"] = [_to_risk_dict(rd, signal, candidate_obj)]

    order_type = OrderType.MARKET
    audit["order_intents"] = [_order_intent_dict(signal=signal, risk_decision=rd, qty=qty, price=current_price, order_type=order_type)]
    audit["actual_order_submitted"] = False
    if not bool(getattr(rd, "allowed", False)):
        audit["next_blocking_point"] = "risk(rejected)"
    return audit
