# SAT3 전체 개발 프로세스 정리

> 작성일: 2026-05-05
> 최종 커밋: 1b227a1
> 최종 테스트: 1183 passed

---

## 프로세스 플로우시트

```
Phase 1~4                         N4~N7                            N8
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 기반구축 │───▶│ KIS 연동 │───▶│ REST 검증│───▶│RealTrans │───▶│ WS 기반  │
│ Scanner  │    │ Adapter  │    │ Query    │    │ port구현 │    │ Foundation│
│ Quant    │    │ Token    │    │ Facade   │    │ KisClient│    │ ws_models│
│ Strategy │    │ Endpoint │    │ Read-only│    │ routing  │    │ parser   │
│ Risk     │    │ Catalog  │    │ Guard    │    │ endpoint │    │ client   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
Phase 5~9         N5 DB           N6 Manual       N7-B~D           N8-B~C
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Order    │    │ SQLite   │    │ .env      │    │ Parser   │    │ WS Smoke │
│ Portfolio│    │ 10 tables│    │ 예시작성  │    │ 보정      │    │ 준비     │
│ EOD      │    │ 10 Repos │    │ smoke     │    │ 실제응답  │    │ Real WS  │
│ Release  │    │ InMemory │    │ script    │    │ endpoint  │    │ connect  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
  N1~N3            N9               N10             N11~12          N13~18
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 운영문서  │    │Data Router│   │ Frontend  │    │Dry-Runner │   │SafetyGate│
│ Dashboard│    │REST+WS    │    │ Dashboard │    │ Scheduler │    │Order API │
│ Telegram │    │ 캐시통합  │    │ Vite+React│    │Orchestrtr │    │Fill/Pstn │
│ 이벤트   │    │DataQuality│   │ 9 comps   │    │Runtime    │    │Exit/Anal │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
  OPS-1~2         OPS-3          OPS-PREP        OPS-문서
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ WS real  │    │Dashboard  │    │Preflight  │    │운영스케줄│
│ connect  │    │ Enhance   │    │Launcher   │    │날짜체크  │
│ 구현     │    │ Log/TG/KIS│    │EmergStop  │    │실행명령  │
│ websocket│    │ Account   │    │DashHealth │    │모음      │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

---

## Phase 1 — 기반 아키텍처

| 항목 | 설명 |
|------|------|
| 프로젝트 구조 | backend/ 디렉토리, 패키지 구성 |
| KisCredentials | 인증 정보 관리 (app_key, app_secret, account_no) |
| SourcePolicy | KIS_API_REST / KIS_API_WS 단일 출처 정책 |
| AuditEvent | 감사 로그 이벤트 모델 |
| DataUnavailable | 추정값 금지, 실패 시 명시적 타입 |

## Phase 2 — Scanner Engine

| 항목 | 설명 |
|------|------|
| ScannerType | RAPID_SURGE, LIQUIDITY_MOMENTUM, BREAKOUT, PULLBACK_REBOUND |
| ExclusionReason | ETF/ETN/ELW/REIT/SPAC/우선주 등 20종 제외 사유 |
| Universe | KOSPI/KOSDAQ 보통주 필터 |
| scanner_engine | 종목 스캔 실행 |
| scanner_audit | 스캔 결과 AuditEvent |

## Phase 3 — Quant Engine

| 항목 | 설명 |
|------|------|
| QuantScore | 유동성/모멘텀/기술적 점수 종합 |
| QuantDecision | PASS / WATCH / REJECT |
| scoring_config | 전략별 가중치 설정 |
| quant_audit | 평가 결과 AuditEvent |

## Phase 4 — Strategy / Risk Engine

| 항목 | 설명 |
|------|------|
| StrategyType | 4 entry + 1 exit (RAPID_SURGE_SCALPING, LIQUIDITY_MOMENTUM_FOLLOW, BREAKOUT_FOLLOW, PULLBACK_REBOUND, FAST_EXIT) |
| StrategyPolicy | Market Regime별 전략 활성 정책 (BULL/NEUTRAL/BEAR/UNKNOWN) |
| RiskEngine | 13종 거절 사유 검사 |
| RiskLimits | 종목당 ₩1,000만, 일일손실 예수금 5% |
| risk_audit | 리스크 판단 AuditEvent |

## Phase 5 — Order / Live Gate

| 항목 | 설명 |
|------|------|
| LiveOrderGate | 6단계 검증 (Live=false 차단) |
| OrderIntent | 주문 의도 (제출 전) |
| OrderSubmitResult | 주문 접수 결과 |

## Phase 6 — Portfolio

| 항목 | 설명 |
|------|------|
| PortfolioView | 보유 종목, 수량, 평균가, 평가손익 |
| Position | 포지션 상태 |

## Phase 7 — EOD Report

| 항목 | 설명 |
|------|------|
| EODReport | 일일 승률, PnL, Profit Factor, 손익 요약 |

## Phase 8 — Release Gate / Safety

| 항목 | 설명 |
|------|------|
| Preflight | 모듈 로드, .env 체크, secret 미출력 |
| ReleaseGate | LIVE_TRADING_ENABLED=false, no_fake_fill 등 |
| EmergencyStop | 비상정지 상태 관리 |

## Phase 9 — Integration / Hardening

| 항목 | 설명 |
|------|------|
| 전체 모듈 통합 | Scanner→Quant→Strategy→Risk→Order pipeline |
| pytest | 초기 926개 테스트 |

---

## N1 — 운영 문서

| 항목 | 설명 |
|------|------|
| sat3_operational_runbook.md | 시스템 개요, 파이프라인, 운용 절차 |
| sat3_emergency_stop.md | 비상정지 절차 |
| sat3_strategy_risk_engine.md | 전략/리스크 문서 |

## N2 — Dashboard Foundation

| 항목 | 설명 |
|------|------|
| DashboardModels | SystemStatusView 등 13개 ViewModel |
| DashboardRoutes | 14개 route handler |
| DashboardService | 서비스 계층 |

## N3 — Telegram 이벤트 보완

| 항목 | 설명 |
|------|------|
| telegram_event.py | TelegramEvent 모델, 이벤트 타입 22종 |
| telegram_formatter.py | AuditEvent → Telegram 변환 |
| telegram_policy.py | 알림 정책, Throttling |
| telegram_notifier.py | Policy → Formatter → Sender 파이프라인 |

## N4 — KIS 실제 조회 Adapter

| 항목 | 설명 |
|------|------|
| credentials | KisCredentials.from_env() |
| transport | StubTransport / RealTransport |
| token_provider | /oauth2/tokenP OAuth 발급 |
| market_schedule | 장운영정보 조회 |
| market_data | 현재가 조회 |
| stock_info | 종목정보 조회 |
| account | 계좌 조회 |

## N5 — DB Storage Foundation

| 항목 | 설명 |
|------|------|
| SQLite | 10개 테이블 |
| Repository | 10개 Repository 클래스 |

## N6 — Read-Only Query Facade + Order Guard

| 항목 | 설명 |
|------|------|
| KisClient | 인증 헤더 자동 생성, transport 주입 |
| QueryFacade | 8개 read-only API |
| OrderEndpointBlocked | order-cash/credit/rvsecncl 차단 |

## N6-MANUAL — Read-Only Smoke 준비

| 항목 | 설명 |
|------|------|
| .env.example | 빈 템플릿 |
| kis_readonly_smoke.py | REST read-only smoke |
| 문서 | sat3_kis_readonly_smoke_test.md |

## N7 — RealTransport 구현

| 항목 | 설명 |
|------|------|
| RealTransport | urllib 기반 순수 전송 |
| --real 옵션 | 실제 KIS 호출 (smoke 전용) |

## N7-B — API Parser 보정

| 항목 | 설명 |
|------|------|
| output1/output2 | KIS 실제 응답 필드 처리 |
| fallback | 다중 필드 fallback |

## N7-C — Authenticated KisClient Routing

| 항목 | 설명 |
|------|------|
| client routing | 모든 API → KisClient 경유 |
| transport fallback | StubTransport 유지 |

## N7-D — KIS Endpoint / TR_ID Spec 보정

| 항목 | 설명 |
|------|------|
| endpoint catalog | alias, TR_ID, query params |
| dual mode | client/transport 양쪽 지원 |

---

## N8 — KIS WebSocket Foundation

| 항목 | 설명 |
|------|------|
| ws_models.py | WebSocketMessageBase, RealtimeTradeTick 등 7종 |
| ws_endpoints.py | H0STCNT0, H0STASP0, H0STCNI0, H0STMKO0, H0STANC0 |
| ws_approval.py | approval_key 발급 / masking |
| ws_parser.py | raw → typed model 파서 (JSON + pipe-delimited) |
| ws_client.py | StubWSClient + GuardedRealWSClient |
| ws_event_bridge.py | WS → AuditEvent 변환 |
| ws_subscription.py | SubscribeRequest, build_payload |
| docs | sat3_kis_websocket_foundation.md |

## N8-B — WebSocket Smoke 준비

| 항목 | 설명 |
|------|------|
| kis_ws_readonly_smoke.py | Stub/Real 모드, 채널 선택 |
| docs | sat3_kis_ws_readonly_smoke_test.md |

## N8-C — WebSocket 실제 연결 검증 준비

| 항목 | 설명 |
|------|------|
| GuardedRealWSClient 보완 | heartbeat, connection_state |
| pipe-delimited parser | KIS pipe format 지원 |
| --duration, --max-messages | smoke 옵션 확장 |
| docs | sat3_kis_ws_real_smoke_test.md |

---

## N9 — REST + WebSocket Data Router

| 항목 | 설명 |
|------|------|
| data_router.py | MarketDataRouter: get_latest_* |
| market_cache.py | symbol별 cache (trade_tick, orderbook, status) |
| data_quality.py | stale, missing, source mismatch |
| rest_ws_policy.py | 초기값 REST, 실시간 WS, fallback |
| docs | sat3_rest_ws_data_router.md |

## N10 — Frontend Dashboard

| 항목 | 설명 |
|------|------|
| Vite + React | frontend/ 프로젝트 |
| 9 components | SystemStatus, Session, Regime, WS, DataRouter, DataQuality, Scanner, Quant, Risk |
| Dark theme | GitHub 스타일 다크 테마 |
| docs | sat3_frontend_dashboard.md |

## N11 — Dry Decision Pipeline

| 항목 | 설명 |
|------|------|
| dry_decision_runner.py | Scanner→Quant→Strategy→Risk→OrderIntent (차단) |
| KOSPI/KOSDAQ 필터 | ETF/ETN/ELW 제외 |
| docs | sat3_live_data_dry_decision.md |

## N12 — Runtime Scheduler

| 항목 | 설명 |
|------|------|
| scheduler.py | SessionState 기반 task plan |
| orchestrator.py | DataRouter + ScannerRuntime + Evaluator |
| docs | sat3_runtime_scheduler.md |

## N13 — Safety Gate

| 항목 | 설명 |
|------|------|
| LiveOrderSafetyGate | 10-layer (LIVE, EmergencyStop, Session, Regime, Risk, Quote, Orderbook, Loss, Duplicate, WS) |
| SafetyGateCheck | 개별 검증 결과 |
| SafetyGateResult | 종합 결과 + 차단 사유 |

## N14 — KIS Order API

| 항목 | 설명 |
|------|------|
| order_api.py | submit_cash_order (BUY:TTTC0012U, SELL:TTTC0011U) |
| SafetyGate 필수 | approved 아니면 차단 |
| LIVE_TRADING_ENABLED | false면 차단 |

## N15 — Fill / Position Reconciliation

| 항목 | 설명 |
|------|------|
| fill_reconciliation.py | WS fill notice + REST fills + REST balance 3-way |
| 주문접수 ≠ 체결성공 | 명확히 분리 |

## N16 — Exit Strategy

| 항목 | 설명 |
|------|------|
| exit_strategy.py | StopLoss(-3%), TakeProfit(+5%), TrailingStop(-2%) |
| SafetyGate | Exit도 SafetyGate 통과 필요 |

## N17 — Small Live Order Validation

| 항목 | 설명 |
|------|------|
| sat3_live_order_smoke.py | --confirm-live-order 필수, --dry-run 기본 |
| 1주 단위 검증 | 선택적 (강제 아님) |

## N18 — Performance Analytics

| 항목 | 설명 |
|------|------|
| performance_analyzer.py | 승률, Profit Factor, PnL, Drawdown |
| 전략/Regime별 | 그룹핑 분석 |

---

## OPS-1 — KIS REST Read-Only Smoke 검증

| 항목 | 설명 |
|------|------|
| REST smoke 실전행 | --real 옵션 |
| Token 발급 / 현재가 / 잔고 | KIS API 응답 확인 |
| 403 분석 | IP 화이트리스트 / 휴장일 이슈 |

## OPS-2 — WebSocket 실제 연결 활성화

| 항목 | 설명 |
|------|------|
| websocket-client | 의존성 추가 (requirements.txt) |
| GuardedRealWSClient.connect() | 실제 연결 구현 |
| --real-ws smoke | 수동 smoke 전용 |

## OPS-3 — Dashboard Enhancement

| 항목 | 설명 |
|------|------|
| LogSystem | daily_logger.py (날짜별/카테고리별 8종) |
| TelegramStatusCard | 봇 연결 상태 |
| KisAccountCard | 계좌 정보 (KIS API 연동) |
| DailySummaryCard | 일일 승률/PnL |
| StrategyBreakdownTable | 전략별 성과 |
| LogViewer | 날짜선택 + 섹션탭 |
| DateTimeCard | 실시간 날짜/시간/세션 |
| 한글화 | 전체 대시보드 한글 전환 |
| Telegram 알림 | 18종 한글 알림 (HTML) |
| Server 알림 | 백엔드 시작 시 자동 발송 |

## OPS-PREP — 개장일 준비

| 항목 | 설명 |
|------|------|
| sat3_preflight_check.py | 로컬 환경 점검 |
| sat3_market_open_launcher.py | 9단계 가이드 launcher |
| sat3_emergency_stop_cli.py | 비상정지 CLI |
| sat3_dashboard_health_check.py | Dashboard 점검 |
| sat3_date_check.py | 날짜/시간/세션 확인 |
| sat3_market_open_runbook.md | 개장일 타임라인 |
| sat3_daily_operation_schedule.md | 상세 운영 스케줄 |

---

## 최종 통계

| 항목 | 값 |
|------|-----|
| 총 커밋 수 | 42 |
| 총 파일 수 | 100+ |
| 총 테스트 수 | 1,183 |
| Python 패키지 | 18개 |
| Frontend 컴포넌트 | 15개 |
| Telegram 알림 | 18종 |
| SafetyGate Layer | 10-layer |
| 문서 | 25+ |
