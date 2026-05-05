"""Dashboard Service — InMemory 데이터 조회

실제 DB/KIS 연결 전까지는 Stub/InMemory 기반.
모든 조회는 Read-Only — 주문 실행 없음.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from dashboard.dashboard_models import (
    SystemStatusView, SessionStatusView, MarketRegimeView,
    ScannerCandidateView, QuantScoreView, StrategySignalView,
    RiskDecisionView, OrderStatusView, FillStatusView,
    PortfolioView, EodReportView, AuditTimelineView,
    DashboardSummary,
)


class DashboardService:
    """대시보드 데이터 서비스 — InMemory 저장소 기반 + Repository 주입"""

    def __init__(self):
        self._candidates: list[ScannerCandidateView] = []
        self._quant_scores: list[QuantScoreView] = []
        self._strategy_signals: list[StrategySignalView] = []
        self._risk_decisions: list[RiskDecisionView] = []
        self._orders: list[OrderStatusView] = []
        self._fills: list[FillStatusView] = []
        self._portfolio: list[PortfolioView] = []
        self._audit_events: list[AuditTimelineView] = []
        self._audit_event_payloads: dict[str, dict[str, Any]] = {}
        self._audit_repo = None
        self._ws_status_provider = None
        self._session_status_override: SessionStatusView | None = None
        self._market_regime_override: MarketRegimeView | None = None

    # ── 데이터 주입 (Stub 용) ──

    def inject_candidates(self, items: list[ScannerCandidateView]) -> None:
        self._candidates = items

    def inject_risk_decisions(self, items: list[RiskDecisionView]) -> None:
        self._risk_decisions = items

    def inject_audit_events(self, items: list[AuditTimelineView]) -> None:
        self._audit_events = items

    def inject_audit_event_payloads(self, payloads: dict[str, dict[str, Any]]) -> None:
        """Inject sanitized payloads keyed by event_id (stub/testing).

        NOTE: payloads must be sanitized already or will be sanitized at read time.
        """
        self._audit_event_payloads = dict(payloads)

    def inject_session_status(self, status: SessionStatusView) -> None:
        self._session_status_override = status

    def inject_market_regime(self, regime: MarketRegimeView) -> None:
        self._market_regime_override = regime

    # ── Repository 주입 (DB 연결) ──

    def set_audit_repository(self, repo) -> None:
        self._audit_repo = repo

    def set_ws_status_provider(self, provider) -> None:
        """Inject a runtime ws status provider.

        Provider must return sanitized status dict (no secrets, no raw frames).
        """
        self._ws_status_provider = provider

    def get_ws_status(self) -> dict:
        """Return websocket connection status for dashboard.

        If provider is missing, return safe status + reason.
        """
        if self._ws_status_provider is None:
            return {
                "connection_state": "UNKNOWN",
                "subscribed_channels": [],
                "data_source": "default",
                "status_reason": "ws_status_provider_not_configured",
            }
        try:
            status = self._ws_status_provider.get_status()
            if not isinstance(status, dict):
                return {
                    "connection_state": "UNKNOWN",
                    "subscribed_channels": [],
                    "data_source": "provider",
                    "status_reason": "ws_status_provider_invalid_return",
                }
            status.setdefault("subscribed_channels", [])
            status.setdefault("data_source", "provider")
            return status
        except Exception as e:
            return {
                "connection_state": "UNKNOWN",
                "subscribed_channels": [],
                "data_source": "provider",
                "status_reason": f"provider_error:{type(e).__name__}",
            }

    def _timeline_view_from_repo_row(self, row: dict[str, Any]) -> AuditTimelineView:
        """Convert repository row -> AuditTimelineView."""
        return AuditTimelineView(
            event_type=row.get("event_type", ""),
            correlation_id=row.get("correlation_id", "") or "",
            symbol=row.get("symbol", "") or "",
            timestamp=row.get("event_time", "") or row.get("created_at", "") or "",
            event_id=row.get("event_id", "") or "",
            severity=row.get("severity", "INFO") or "INFO",
            source=row.get("source", "") or "",
            strategy_name=row.get("strategy_name", "") or "",
            status=row.get("status", "") or "",
            summary=row.get("summary", "") or "",
            has_checklist=bool(row.get("has_checklist", 0)),
        )

    # ── 조회 ──

    def get_system_status(self) -> SystemStatusView:
        return SystemStatusView(
            live_trading_enabled=False,
            emergency_stop=False,
            modules_loaded=True,
            total_tests=769,
        )

    def get_session_status(self) -> SessionStatusView:
        # 추정 금지: 시간/휴장일 하드코딩 계산으로 상태를 단정하지 않는다.
        # 실소스가 없으면 UNKNOWN + 차단으로만 노출한다.
        if self._session_status_override is not None:
            return self._session_status_override

        return SessionStatusView(
            session_state="UNKNOWN",
            buy_allowed=False,
            is_trading_day=False,
            reason="session_source_unavailable",
            detail="시장세션 데이터 소스 미연결 — 신규매수 차단(조회전용)",
        )

    def get_market_regime(self) -> MarketRegimeView:
        # 추정 금지: 시간/요일 기반 더미 BULL 판정 금지.
        if self._market_regime_override is not None:
            return self._market_regime_override

        return MarketRegimeView(
            regime="UNKNOWN",
            allow_new_buy=False,
            total_score=0.0,
            candidate_score_adjustment=0.0,
            reason="market_regime_source_unavailable",
            factors="실시간 시장 데이터 소스 미연결 — 점수 산출 보류",
        )

    def get_candidates(self) -> list[ScannerCandidateView]:
        return self._candidates

    def get_quant_scores(self) -> list[QuantScoreView]:
        return self._quant_scores

    def get_strategy_signals(self) -> list[StrategySignalView]:
        return self._strategy_signals

    def get_risk_decisions(self) -> list[RiskDecisionView]:
        return self._risk_decisions

    def get_orders(self) -> list[OrderStatusView]:
        return self._orders

    def get_fills(self) -> list[FillStatusView]:
        return self._fills

    def get_portfolio(self) -> list[PortfolioView]:
        return self._portfolio

    def get_eod_latest(self) -> EodReportView | None:
        return None  # No EOD report yet

    def get_audit_timeline(self, limit: int = 50) -> list[AuditTimelineView]:
        if self._audit_repo is not None:
            rows = self._audit_repo.list_all(limit)
            return [self._timeline_view_from_repo_row(r) for r in rows]
        return self._audit_events[:limit]

    def get_audit_by_correlation(self, correlation_id: str) -> list[AuditTimelineView]:
        if self._audit_repo is not None:
            rows = self._audit_repo.find_by_correlation(correlation_id, limit=200)
            return [self._timeline_view_from_repo_row(r) for r in rows]
        return [e for e in self._audit_events if e.correlation_id == correlation_id]

    def get_audit_event_detail(self, event_id: str) -> dict[str, Any]:
        """Audit event detail (read-only).

        - Returns sanitized payload JSON (local-only advanced/debug UI)
        - Returns checklist if the payload contains one
        - Never returns raw REST response bodies or raw WebSocket full messages
        """
        from audit_logging.log_sanitizer import sanitize_dict

        timeline = None
        payload_sanitized: dict[str, Any] = {}

        if self._audit_repo is not None:
            row = self._audit_repo.get_by_event_id(event_id)
            if row is None:
                return {"error": "not_found", "event_id": event_id}

            timeline = self._timeline_view_from_repo_row(row)

            raw_payload = row.get("payload", "{}")
            try:
                import json
                payload_obj = json.loads(raw_payload) if isinstance(raw_payload, str) else {}
            except Exception:
                payload_obj = {}
            payload_sanitized = sanitize_dict(payload_obj) if isinstance(payload_obj, dict) else {}
        else:
            timeline = next((e for e in self._audit_events if e.event_id == event_id), None)
            payload = self._audit_event_payloads.get(event_id, {})
            payload_sanitized = sanitize_dict(payload) if isinstance(payload, dict) else {}

        checklist = None
        if isinstance(payload_sanitized, dict):
            cl = payload_sanitized.get("checklist")
            if isinstance(cl, dict):
                checklist = cl

        related = []
        if timeline and timeline.correlation_id:
            related_events = self.get_audit_by_correlation(timeline.correlation_id)
            # prevent huge payloads
            related_events = related_events[:200]
            related = [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "timestamp": e.timestamp,
                    "symbol": e.symbol,
                    "strategy_name": e.strategy_name,
                    "status": e.status,
                    "summary": e.summary,
                    "correlation_id": e.correlation_id,
                }
                for e in related_events
            ]

        return {
            "event_id": event_id,
            "correlation_id": timeline.correlation_id if timeline else "",
            "event_type": timeline.event_type if timeline else "",
            "severity": timeline.severity if timeline else "INFO",
            "timestamp": timeline.timestamp if timeline else "",
            "symbol": timeline.symbol if timeline else "",
            "strategy_name": timeline.strategy_name if timeline else "",
            "status": timeline.status if timeline else "",
            "summary": timeline.summary if timeline else "",
            "checklist": checklist,
            "payload_sanitized": payload_sanitized,
            "related_events": related,
        }
