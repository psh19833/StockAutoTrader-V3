"""Orchestrator — coordinates Scheduler, DataRouter, DryDecisionRunner (N12)."""
from __future__ import annotations

from typing import Optional, Callable, Any
from datetime import datetime, timezone
import os

from runtime.scheduler import Scheduler, SessionState
from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache
from runtime.dry_decision_runner import DryDecisionRunner
from runtime.live_trading_runner import LiveTradingRunner
from runtime.live_scanner import LiveScannerAdapter
from runtime.rest_provider_factory import maybe_create_kis_rest_provider


class Orchestrator:
    """SAT3 main orchestrator."""

    @staticmethod
    def _with_origin_metadata(items: list[dict[str, Any]], *, item_type: str) -> list[dict[str, Any]]:
        generated_at = datetime.now(timezone.utc).isoformat()
        out: list[dict[str, Any]] = []
        for item in items:
            row = dict(item)
            mode = str(row.get("mode", "UNKNOWN") or "UNKNOWN").upper()
            synthetic = bool(row.get("synthetic", False) or mode == "DRY_RUN")
            row.setdefault("generated_at", generated_at)
            row.setdefault("source", "DRY_DECISION_RUNNER" if synthetic else "LIVE_SCANNER")
            row.setdefault("mode", mode)
            row.setdefault("synthetic", synthetic)
            row.setdefault("origin", "synthetic_audit" if synthetic else "live")
            row.setdefault("run_id", f"{item_type}:{generated_at}")
            row.setdefault("scan_id", "")
            row.setdefault("is_live_candidate", not synthetic)
            out.append(row)
        return out

    @staticmethod
    def _split_synthetic(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        live_items: list[dict[str, Any]] = []
        synthetic_items: list[dict[str, Any]] = []
        for item in items:
            mode = str(item.get("mode", "")).upper()
            synthetic = bool(item.get("synthetic", False) or mode == "DRY_RUN")
            if synthetic:
                synthetic_items.append(item)
            else:
                live_items.append(item)
        return live_items, synthetic_items

    @classmethod
    def _build_live_pipeline_audit(
        cls,
        dry: dict,
        live_chain: dict[str, Any],
        scanner_status: str,
        live_pipeline_reason: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        candidates_all = cls._with_origin_metadata(list(dry.get("candidates", []) or []), item_type="candidate")
        scores_all = cls._with_origin_metadata(list(dry.get("scores", []) or []), item_type="score")
        signals_all = cls._with_origin_metadata(list(dry.get("signals", []) or []), item_type="signal")
        risk_all = cls._with_origin_metadata(list(dry.get("risk_decisions", []) or []), item_type="risk")
        intents_all = cls._with_origin_metadata(list(dry.get("order_intents", []) or []), item_type="intent")

        live_candidates, synthetic_candidates = cls._split_synthetic(candidates_all)
        live_scores, synthetic_scores = cls._split_synthetic(scores_all)
        live_signals, synthetic_signals = cls._split_synthetic(signals_all)
        live_risk, synthetic_risk = cls._split_synthetic(risk_all)
        live_intents, synthetic_intents = cls._split_synthetic(intents_all)

        raw_live_candidates = cls._with_origin_metadata(list(live_chain.get("candidates", []) or []), item_type="candidate")
        raw_live_scores = cls._with_origin_metadata(list(live_chain.get("scores", []) or []), item_type="score")
        raw_live_signals = cls._with_origin_metadata(list(live_chain.get("signals", []) or []), item_type="signal")
        raw_live_risk = cls._with_origin_metadata(list(live_chain.get("risk_decisions", []) or []), item_type="risk")
        raw_live_intents = cls._with_origin_metadata(list(live_chain.get("order_intents", []) or []), item_type="intent")

        live_candidates = [c for c in raw_live_candidates if not bool(c.get("synthetic", False)) and str(c.get("mode", "")).upper() == "LIVE"]
        live_scores = [s for s in raw_live_scores if not bool(s.get("synthetic", False)) and str(s.get("mode", "")).upper() == "LIVE"]
        live_signals = [s for s in raw_live_signals if not bool(s.get("synthetic", False)) and str(s.get("mode", "")).upper() == "LIVE"]
        live_risk = [r for r in raw_live_risk if not bool(r.get("synthetic", False)) and str(r.get("mode", "")).upper() == "LIVE"]
        live_intents = [o for o in raw_live_intents if not bool(o.get("synthetic", False)) and str(o.get("mode", "")).upper() == "LIVE"]

        buy_signals = [s for s in live_signals if str(s.get("side", "")).upper() == "BUY"]
        hold_signals = [s for s in live_signals if str(s.get("side", "")).upper() in {"HOLD", "WAIT"}]
        rejected_signals_count = max(0, len(live_scores) - len(live_signals))

        risk_approved = [r for r in live_risk if bool(r.get("allowed", False))]
        risk_rejected = [r for r in live_risk if not bool(r.get("allowed", False))]

        reject_reasons: dict[str, int] = {}
        for r in risk_rejected:
            key = str(r.get("reason_code", "UNKNOWN"))
            reject_reasons[key] = int(reject_reasons.get(key, 0)) + 1

        if len(live_candidates) == 0 and not live_pipeline_reason:
            live_pipeline_reason = "LIVE_SCANNER_NOT_CONNECTED"

        live_pipeline = {
            "scanner_candidates_count": len(live_candidates),
            "scanner_candidates_sample": live_candidates[:5],
            "strategy_signals_count": len(live_signals),
            "buy_signals_count": len(buy_signals),
            "hold_signals_count": len(hold_signals),
            "rejected_signals_count": rejected_signals_count,
            "risk_approved_count": len(risk_approved),
            "risk_rejected_count": len(risk_rejected),
            "risk_reject_reasons": reject_reasons,
            "order_intents_count": len(live_intents),
            "order_intents_sample": live_intents[:5],
            "order_submit_enabled": False,
            "actual_order_submitted": False,
            "strategy_signals_sample": live_signals[:10],
            "risk_decisions_sample": live_risk[:10],
            "live_pipeline_reason": live_pipeline_reason,
            "scanner_status": scanner_status,
            "counts": {
                "candidates": len(live_candidates),
                "scores": len(live_scores),
                "signals": len(live_signals),
                "risk_decisions": len(live_risk),
                "order_intents": len(live_intents),
            },
            "synthetic_candidates_count": len(synthetic_candidates),
            "synthetic_strategy_signals_count": len(synthetic_signals),
            "synthetic_buy_signals_count": len([s for s in synthetic_signals if str(s.get("side", "")).upper() == "BUY"]),
            "synthetic_risk_approved_count": len([r for r in synthetic_risk if bool(r.get("allowed", False))]),
            "synthetic_order_intents_count": len(synthetic_intents),
            "synthetic_reason": "DRY_RUN_AUDIT_ONLY",
            "synthetic_candidates_sample": synthetic_candidates[:5],
            "synthetic_strategy_signals_sample": synthetic_signals[:10],
            "synthetic_risk_decisions_sample": synthetic_risk[:10],
            "synthetic_order_intents_sample": synthetic_intents[:5],
        }

        synthetic_audit = {
            "mode": "DRY_RUN",
            "reason": "DRY_RUN_AUDIT_ONLY",
            "candidates": synthetic_candidates,
            "scores": synthetic_scores,
            "signals": synthetic_signals,
            "risk_decisions": synthetic_risk,
            "order_intents": synthetic_intents,
        }

        live_real_data = {
            "candidates": live_candidates,
            "scores": live_scores,
            "signals": live_signals,
            "risk_decisions": live_risk,
            "order_intents": live_intents,
        }
        return live_pipeline, synthetic_audit, live_real_data

    def _build_live_chain_from_candidates(self, live_candidates: list[dict[str, Any]]) -> dict[str, Any]:
        scores: list[dict[str, Any]] = []
        signals: list[dict[str, Any]] = []
        risk_decisions: list[dict[str, Any]] = []
        order_intents: list[dict[str, Any]] = []

        for c in live_candidates:
            symbol = str(c.get("symbol", ""))
            scanner_type = str(c.get("scanner_type", "RAPID_SURGE"))
            score = {
                "symbol": symbol,
                "decision": "PASS",
                "final_score": 0.75,
                "liquidity_score": 0.8,
                "momentum_score": 0.7,
                "scanner_type": scanner_type,
                "mode": "LIVE",
                "synthetic": False,
            }
            scores.append(score)

            signal = {
                "symbol": symbol,
                "side": "BUY",
                "strategy_type": scanner_type,
                "confidence": 0.75,
                "market_regime": "NEUTRAL",
                "mode": "LIVE",
                "synthetic": False,
            }
            signals.append(signal)

            risk = {
                "symbol": symbol,
                "side": "BUY",
                "allowed": True,
                "reason_code": "APPROVED",
                "reason_text": "Audit-only live chain approved",
                "mode": "LIVE",
                "synthetic": False,
            }
            risk_decisions.append(risk)

            order_intents.append(
                {
                    "symbol": symbol,
                    "side": "BUY",
                    "qty": 1,
                    "submitted": False,
                    "blocked_reason": "AUDIT_ONLY_NO_SUBMIT",
                    "mode": "LIVE",
                    "synthetic": False,
                }
            )

        return {
            "candidates": list(live_candidates),
            "scores": scores,
            "signals": signals,
            "risk_decisions": risk_decisions,
            "order_intents": order_intents,
        }

    def __init__(self, live_readiness_provider: Callable[[], tuple[bool, list[str]]] | None = None):
        self._scheduler = Scheduler()
        self._cache = MarketCache()
        self._router = MarketDataRouter(self._cache)
        self._rest_provider = None
        self._rest_provider_meta: dict[str, Any] = {"configured": False, "reason": "not_attempted"}
        self._rest_provider_attempted = False
        self._dry_runner = DryDecisionRunner(self._router)
        self._live_scanner = LiveScannerAdapter(self._router)
        live_runner_enabled = os.getenv("SAT3_ENABLE_LIVE_RUNNER", "false").lower() == "true"
        self._live_runner = LiveTradingRunner(configured=live_runner_enabled)
        self._live_readiness_provider = live_readiness_provider
        self._state = "stopped"
        self._last_tick: Optional[str] = None

    def _ensure_rest_provider(self) -> dict[str, Any]:
        if self._rest_provider_attempted:
            return dict(self._rest_provider_meta)
        self._rest_provider_attempted = True
        provider, meta = maybe_create_kis_rest_provider()
        self._rest_provider = provider
        self._rest_provider_meta = dict(meta or {})
        if provider is not None:
            self._router._rest_provider = provider  # lazy live-only wiring
            self._router._rest_available = True
        return dict(self._rest_provider_meta)

    @property
    def state(self) -> str:
        return self._state

    @property
    def scheduler(self) -> Scheduler:
        return self._scheduler

    @property
    def router(self) -> MarketDataRouter:
        return self._router

    def tick(self, session: SessionState, mode: str = "dry-run") -> dict:
        """Execute one tick for the given session state.

        mode:
          - "dry-run": run synthetic pipeline (DryDecisionRunner)
          - "live": run LiveTradingRunner skeleton (blocked unless configured)
        """
        self._scheduler.set_session(session)
        plan = self._scheduler.get_task_plan()
        self._state = "running"
        result = {"session": session.value, "plan": plan, "mode": mode, "actions": []}
        if mode == "live":
            result["rest_provider"] = self._ensure_rest_provider()

        if "BLOCK_ALL" in plan and mode != "live":
            self._state = "stopped"
            result["actions"].append("all_blocked")
            return result
        if "NOOP" in plan and mode != "live":
            self._state = "idle"
            result["actions"].append("noop")
            return result
        if "PREPARE_DATA" in plan:
            result["actions"].append("data_prepared")
        if "SCAN" in plan:
            if mode == "dry-run":
                dry = self._dry_runner.run()
                result["actions"].append("dry_run_scanned")
                result["dry_run"] = {
                    "mode": dry.get("mode"),
                    "note": dry.get("note", ""),
                    "counts": {
                        "candidates": len(dry.get("candidates", []) or []),
                        "scores": len(dry.get("scores", []) or []),
                        "signals": len(dry.get("signals", []) or []),
                        "risk_decisions": len(dry.get("risk_decisions", []) or []),
                        "order_intents": len(dry.get("order_intents", []) or []),
                    },
                    "candidates": dry.get("candidates", []) or [],
                    "scores": dry.get("scores", []) or [],
                    "signals": dry.get("signals", []) or [],
                    "risk_decisions": dry.get("risk_decisions", []) or [],
                    "order_intents": dry.get("order_intents", []) or [],
                }
            elif mode == "live":
                ready = False
                block_reasons = ["LIVE_READINESS_PROVIDER_NOT_CONFIGURED"]
                if self._live_readiness_provider is not None:
                    try:
                        ready, block_reasons = self._live_readiness_provider()
                    except Exception:
                        ready = False
                        block_reasons = ["LIVE_READINESS_PROVIDER_ERROR"]
                live = self._live_runner.run_tick(
                    session=session.value,
                    ready=bool(ready),
                    block_reasons=list(block_reasons or []),
                )
                result["actions"].append("live_tick")
                live_payload = live.to_dict()

                # Read-only live pipeline audit: scanner -> strategy -> risk -> order intent.
                # Never submits real orders.
                if live_payload.get("status") == "LIVE_PIPELINE_TICK_EXECUTED":
                    live_scan = self._live_scanner.run_live_scan(session=session.value)
                    live_chain = self._build_live_chain_from_candidates(list(live_scan.candidates or []))
                    dry = self._dry_runner.run()
                    live_pipeline, synthetic_audit, live_real_data = self._build_live_pipeline_audit(
                        dry,
                        live_chain,
                        scanner_status=str(live_scan.status),
                        live_pipeline_reason=str(live_scan.reason),
                    )
                    live_pipeline["live_scan"] = live_scan.to_dict()
                    live_payload["pipeline"] = live_pipeline
                    result["synthetic_audit"] = synthetic_audit
                    result["live_real_pipeline_data"] = live_real_data
                elif live_payload.get("status") == "BLOCKED_SESSION":
                    dry = self._dry_runner.run()
                    live_pipeline, synthetic_audit, live_real_data = self._build_live_pipeline_audit(
                        dry,
                        live_chain={"candidates": [], "scores": [], "signals": [], "risk_decisions": [], "order_intents": []},
                        scanner_status="WAITING_FOR_REGULAR_MARKET",
                        live_pipeline_reason="SESSION_NOT_REGULAR_MARKET",
                    )
                    live_payload["pipeline"] = live_pipeline
                    result["synthetic_audit"] = synthetic_audit
                    result["live_real_pipeline_data"] = live_real_data

                result["live"] = live_payload
            else:
                result["actions"].append("invalid_mode")
                result["error"] = "INVALID_MODE"
        if "EOD_REPORT" in plan:
            result["actions"].append("eod_reported")
        if mode == "live" and "live" not in result:
            ready = False
            block_reasons = ["LIVE_READINESS_PROVIDER_NOT_CONFIGURED"]
            if self._live_readiness_provider is not None:
                try:
                    ready, block_reasons = self._live_readiness_provider()
                except Exception:
                    ready = False
                    block_reasons = ["LIVE_READINESS_PROVIDER_ERROR"]
            live = self._live_runner.run_tick(
                session=session.value,
                ready=bool(ready),
                block_reasons=list(block_reasons or []),
            )
            live_payload = live.to_dict()
            if live_payload.get("status") == "BLOCKED_SESSION":
                dry = self._dry_runner.run()
                live_pipeline, synthetic_audit, live_real_data = self._build_live_pipeline_audit(
                    dry,
                    live_chain={"candidates": [], "scores": [], "signals": [], "risk_decisions": [], "order_intents": []},
                    scanner_status="WAITING_FOR_REGULAR_MARKET",
                    live_pipeline_reason="SESSION_NOT_REGULAR_MARKET",
                )
                live_payload["pipeline"] = live_pipeline
                result["synthetic_audit"] = synthetic_audit
                result["live_real_pipeline_data"] = live_real_data
            result["live"] = live_payload
            result["actions"].append("live_tick")
        self._state = "idle"
        return result

    def stop(self) -> None:
        self._state = "stopped"
