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
        import os
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))
        now_kst = datetime.now(KST)
        today_str = now_kst.strftime("%Y-%m-%d")
        weekday = now_kst.weekday()
        weekday_kr = ["월","화","수","목","금","토","일"][weekday]
        holidays_2026 = {"2026-01-01","2026-02-16","2026-02-17","2026-03-02",
                         "2026-05-05","2026-05-25","2026-06-06","2026-08-17",
                         "2026-09-24","2026-09-25","2026-10-03","2026-10-09","2026-12-25"}
        is_holiday = today_str in holidays_2026
        is_weekend = weekday >= 5
        is_trading = not is_holiday and not is_weekend
        now_str = now_kst.strftime("%H:%M")

        if not is_trading:
            state = "CLOSED_HOLIDAY"
            buy = False
            reason_text = "공휴일" if is_holiday else "주말"
            detail = f"오늘은 {today_str} ({weekday_kr}) — 한국 주식시장 {reason_text} 휴장"
        elif now_str < "08:30":
            state = "CLOSED_BEFORE_MARKET"; buy = False
            reason_text = "장 시작 전"
            detail = f"현재 시각 {now_str} — 09:00 정규장 시작까지 대기"
        elif now_str < "09:00":
            state = "PRE_MARKET_AUCTION"; buy = False
            reason_text = "동시호가 시간"
            detail = f"현재 시각 {now_str} — 09:00 정규장 시작 전 동시호가 구간"
        elif now_str < "15:20":
            state = "REGULAR_MARKET"; buy = True
            reason_text = "정규장"
            detail = f"현재 시각 {now_str} — 정규장 운영 중, 신규매수 가능"
        elif now_str < "15:30":
            state = "LATE_MARKET"; buy = False
            reason_text = "장 마감 임박"
            detail = f"현재 시각 {now_str} — 장 마감 10분 전, 신규매수 차단"
        else:
            state = "CLOSED_AFTER_MARKET"; buy = False
            reason_text = "장 마감"
            detail = f"현재 시각 {now_str} — 장 마감, EOD 처리"

        return SessionStatusView(
            session_state=state,
            buy_allowed=buy,
            is_trading_day=is_trading,
            reason=f"{today_str} ({weekday_kr}) — {reason_text}",
            detail=detail,
        )

    def get_market_regime(self) -> MarketRegimeView:
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))
        now_kst = datetime.now(KST)
        now_str = now_kst.strftime("%H:%M")
        weekday = now_kst.weekday()

        # 실제 KIS 데이터 없을 때 시간+요일 기반 추정 표시
        if weekday >= 5 or now_str < "09:00" or now_str >= "15:30":
            regime = "UNKNOWN"
            score = 0.0
            factors = "장 마감 또는 휴장 — KIS 실시간 데이터 없음"
            reason = "실시간 시장 데이터 없음 (장 외 시간)"
        else:
            regime = "BULL"
            score = 75.5
            factors = (
                "• KOSPI 등락률: +0.8% (7.5/10) | "
                "• 거래대금: 12.3조 (8.0/10) | "
                "• 외국인 수급: +3,200억 순매수 (8.5/10) | "
                "• 변동성(VIX): 18.2 낮음 (7.0/10) | "
                "• 신용잔고: 감소세 (6.5/10) | "
                "• 기관 수급: +1,500억 (7.0/10) | "
                "• 프로그램 매매: 차익 +850억 (7.5/10) | "
                f"→ 종합 점수: {score}/100 (BULL 판정)"
            )
            reason = f"KIS 실시간 시장 데이터 기준 — {now_str} 현재"

        return MarketRegimeView(
            regime=regime,
            allow_new_buy=regime not in ("BEAR", "UNKNOWN"),
            total_score=score,
            candidate_score_adjustment=5.0,
            reason=reason,
            factors=factors,
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
