"""Orchestrator — coordinates Scheduler, DataRouter, DryDecisionRunner (N12)."""
from __future__ import annotations

from typing import Optional

from runtime.scheduler import Scheduler, SessionState
from runtime.data_router import MarketDataRouter
from runtime.market_cache import MarketCache
from runtime.dry_decision_runner import DryDecisionRunner


class Orchestrator:
    """SAT3 main orchestrator."""

    def __init__(self):
        self._scheduler = Scheduler()
        self._cache = MarketCache()
        self._router = MarketDataRouter(self._cache)
        self._runner = DryDecisionRunner(self._router)
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

    def tick(self, session: SessionState) -> dict:
        """Execute one tick for the given session state."""
        self._scheduler.set_session(session)
        plan = self._scheduler.get_task_plan()
        self._state = "running"
        result = {"session": session.value, "plan": plan, "actions": []}

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
            self._runner.run()
            result["actions"].append("scanned")
        if "EOD_REPORT" in plan:
            result["actions"].append("eod_reported")
        self._state = "idle"
        return result

    def stop(self) -> None:
        self._state = "stopped"
