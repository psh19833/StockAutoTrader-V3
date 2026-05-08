"""Orchestrator — coordinates Scheduler, DataRouter, DryDecisionRunner (N12)."""
from __future__ import annotations

from typing import Optional, Callable
import os

from runtime.scheduler import Scheduler, SessionState
from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache
from runtime.dry_decision_runner import DryDecisionRunner
from runtime.live_trading_runner import LiveTradingRunner


class Orchestrator:
    """SAT3 main orchestrator."""

    def __init__(self, live_readiness_provider: Callable[[], tuple[bool, list[str]]] | None = None):
        self._scheduler = Scheduler()
        self._cache = MarketCache()
        self._router = MarketDataRouter(self._cache)
        self._dry_runner = DryDecisionRunner(self._router)
        live_runner_enabled = os.getenv("SAT3_ENABLE_LIVE_RUNNER", "false").lower() == "true"
        self._live_runner = LiveTradingRunner(configured=live_runner_enabled)
        self._live_readiness_provider = live_readiness_provider
        self._state = "stopped"
        self._last_tick: Optional[str] = None

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

        if "BLOCK_ALL" in plan:
            self._state = "stopped"
            result["actions"].append("all_blocked")
            return result
        if "NOOP" in plan:
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
                result["live"] = live.to_dict()
            else:
                result["actions"].append("invalid_mode")
                result["error"] = "INVALID_MODE"
        if "EOD_REPORT" in plan:
            result["actions"].append("eod_reported")
        self._state = "idle"
        return result

    def stop(self) -> None:
        self._state = "stopped"
