"""Dashboard Service — InMemory 데이터 조회

실제 DB/KIS 연결 전까지는 Stub/InMemory 기반.
모든 조회는 Read-Only — 주문 실행 없음.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os

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
        self._token_provider = None

    def _has_kis_credentials(self) -> bool:
        return bool(os.getenv("KIS_APP_KEY", "") and os.getenv("KIS_APP_SECRET", ""))

    def _data_dir(self) -> Path:
        d = Path(__file__).resolve().parents[2] / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_json_file(self, path: Path) -> dict[str, Any] | None:
        try:
            import json
            if not path.is_file():
                return None
            raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return raw if isinstance(raw, dict) else None
        except Exception:
            return None

    def _load_rest_smoke_snapshot(self) -> dict[str, Any] | None:
        return self._load_json_file(self._data_dir() / "kis_readonly_smoke_snapshot.json")

    def _load_ws_smoke_snapshot(self) -> dict[str, Any] | None:
        return self._load_json_file(self._data_dir() / "kis_ws_readonly_smoke_snapshot.json")

    def _get_token_provider(self):
        if self._token_provider is not None:
            return self._token_provider

        from kis.token_provider import KisTokenProvider
        from kis.transport import RealTransport

        app_key = os.getenv("KIS_APP_KEY", "")
        app_secret = os.getenv("KIS_APP_SECRET", "")
        base_url = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")

        transport = RealTransport(base_url=base_url, timeout=8)
        self._token_provider = KisTokenProvider(
            app_key=app_key,
            app_secret=app_secret,
            base_url=base_url,
            transport=transport,
        )
        return self._token_provider

    def _probe_kis_price(self, symbol: str = "005930") -> dict[str, Any]:
        if not self._has_kis_credentials():
            return {"data_available": False, "reason": "missing_credentials"}
        try:
            import json
            import urllib.request

            app_key = os.getenv("KIS_APP_KEY", "")
            app_secret = os.getenv("KIS_APP_SECRET", "")
            base_url = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")

            token_provider = self._get_token_provider()
            token = token_provider.issue_token()
            access_token = token.access_token
            if not access_token:
                return {"data_available": False, "reason": "token_issue_failed"}

            price_url = (
                f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
                f"?FID_COND_MRKT_DIV_CODE=J&FID_INPUT_ISCD={symbol}"
            )
            req = urllib.request.Request(price_url, method="GET")
            req.add_header("authorization", f"Bearer {access_token}")
            req.add_header("appkey", app_key)
            req.add_header("appsecret", app_secret)
            req.add_header("tr_id", "FHKST01010100")
            resp = urllib.request.urlopen(req, timeout=8)
            body = json.loads(resp.read().decode())
            out = body.get("output") or body.get("output1") or {}
            price = 0
            if isinstance(out, dict):
                v = out.get("stck_prpr") or out.get("prpr") or out.get("current_price") or 0
                try:
                    price = int(float(str(v).replace(",", "")))
                except Exception:
                    price = 0
            if price > 0:
                return {"data_available": True, "symbol": symbol, "current_price": price}
            return {"data_available": False, "reason": "kis_price_unavailable"}
        except Exception as e:
            return {"data_available": False, "reason": f"probe_error:{type(e).__name__}"}

    def get_data_router_status(self) -> dict[str, Any]:
        ws = self.get_ws_status()
        smoke = self._load_rest_smoke_snapshot() or {}
        smoke_ok = bool(smoke.get("success", False))
        smoke_price_ok = str(smoke.get("price", "")).startswith("OK")

        probe = self._probe_kis_price("005930") if not (smoke_ok and smoke_price_ok) else {
            "data_available": True,
            "symbol": str(smoke.get("symbol", "005930")),
            "current_price": int(smoke.get("sample_price", 0) or 0),
            "reason": "rest_smoke_snapshot",
        }
        rest_available = bool(probe.get("data_available", False)) or (smoke_ok and smoke_price_ok)
        rest_reason = str(probe.get("reason", "rest_unavailable"))

        stale_warnings: list[str] = []
        if not rest_available:
            stale_warnings.append(rest_reason)
        elif smoke_ok:
            stale_warnings.append("rest_verified_by_readonly_smoke")

        return {
            "ws_connected": ws.get("connection_state") == "CONNECTED",
            "rest_available": rest_available,
            "stale_warnings": stale_warnings,
            "source": "KIS_API_WS" if ws.get("connection_state") == "CONNECTED" else "KIS_API_REST",
            "sample_symbol": probe.get("symbol", "005930"),
            "sample_price": probe.get("current_price", 0),
        }

    # ── 데이터 주입 (Stub 용) ──

    def inject_candidates(self, items: list[ScannerCandidateView]) -> None:
        self._candidates = items

    def inject_quant_scores(self, items: list[QuantScoreView]) -> None:
        self._quant_scores = items

    def inject_strategy_signals(self, items: list[StrategySignalView]) -> None:
        self._strategy_signals = items

    def inject_risk_decisions(self, items: list[RiskDecisionView]) -> None:
        self._risk_decisions = items

    def inject_orders(self, items: list[OrderStatusView]) -> None:
        self._orders = items

    def inject_fills(self, items: list[FillStatusView]) -> None:
        self._fills = items

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
            ws_smoke = self._load_ws_smoke_snapshot() or {}
            if ws_smoke.get("success") is True:
                return {
                    "connection_state": str(ws_smoke.get("connection_state", "DISCONNECTED")),
                    "subscribed_channels": list(ws_smoke.get("channels", [])),
                    "data_source": "readonly_ws_smoke",
                    "status_reason": "ws_readonly_smoke_verified",
                }
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

    def _parse_bool_env(self, name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on", "y"}

    def _read_emergency_stop_state(self) -> bool:
        """Read project-level emergency stop state file.

        File format:
        - line1: active|inactive
        - line2: reason
        - line3: timestamp
        """
        try:
            state_file = Path(__file__).resolve().parents[2] / ".emergency_stop"
            if not state_file.is_file():
                return False
            first_line = state_file.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
            if not first_line:
                return False
            return first_line[0].strip().lower() == "active"
        except Exception:
            # Dashboard should fail-safe to non-crashing behavior.
            return False

    def get_system_status(self) -> SystemStatusView:
        return SystemStatusView(
            live_trading_enabled=self._parse_bool_env("LIVE_TRADING_ENABLED", default=False),
            emergency_stop=self._read_emergency_stop_state(),
            modules_loaded=True,
            total_tests=769,
        )

    def get_session_status(self) -> SessionStatusView:
        # 추정 금지: 시간/휴장일 하드코딩 계산으로 상태를 단정하지 않는다.
        # 실소스가 없으면 UNKNOWN + 차단으로만 노출한다.
        if self._session_status_override is not None:
            return self._session_status_override

        router = self.get_data_router_status()
        probe = self._probe_kis_price("005930")
        if probe.get("data_available"):
            return SessionStatusView(
                session_state="UNKNOWN",
                buy_allowed=False,
                is_trading_day=True,
                reason="session_status_feed_partial",
                detail=f"KIS 현재가 수신됨(005930={probe.get('current_price', 0)}), 세션상태 판독 어댑터 미연결",
            )

        return SessionStatusView(
            session_state="UNKNOWN",
            buy_allowed=False,
            is_trading_day=False,
            reason="session_source_unavailable",
            detail=f"시장세션 데이터 소스 미연결 — 신규매수 차단(조회전용), data_router.rest_available={router.get('rest_available')} warnings={router.get('stale_warnings')}",
        )

    def get_market_regime(self) -> MarketRegimeView:
        # 추정 금지: 시간/요일 기반 더미 BULL 판정 금지.
        if self._market_regime_override is not None:
            return self._market_regime_override

        router = self.get_data_router_status()
        probe = self._probe_kis_price("005930")
        if probe.get("data_available"):
            return MarketRegimeView(
                regime="UNKNOWN",
                allow_new_buy=False,
                total_score=0.0,
                candidate_score_adjustment=0.0,
                reason="market_regime_feed_partial",
                factors=f"KIS 현재가 수신됨(005930={probe.get('current_price', 0)}), 시장국면 엔진 실데이터 연동 대기",
            )

        return MarketRegimeView(
            regime="UNKNOWN",
            allow_new_buy=False,
            total_score=0.0,
            candidate_score_adjustment=0.0,
            reason="market_regime_source_unavailable",
            factors=f"실시간 시장 데이터 소스 미연결 — 점수 산출 보류, data_router.rest_available={router.get('rest_available')} warnings={router.get('stale_warnings')}",
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
