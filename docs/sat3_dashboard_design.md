# SAT3 Dashboard Design

> SAT3 관제 대시보드 설계 문서
> 마지막 수정: 2026-05-04
> 상태: Backend Foundation 완료, Frontend 미구현 (본 문서로 설계 대체)

---

## 1. Dashboard 목적

SAT3 Dashboard는 운용자가 시스템의 현재 상태를 한눈에 파악할 수 있는 **Read-Only 관제 화면**이다.

### 핵심 원칙

- **주문 실행 버튼 없음** — Dashboard에서 매매 판단/주문 제출 절대 금지
- **LIVE_TRADING_ENABLED 상태 명확 표시** — 실전매매 비활성화 시 붉은 경고
- **Emergency Stop 상태 표시** — 비상정지 활성 시 전면 경고
- **correlation_id로 거래 흐름 추적** — SCAN → QUANT → STRATEGY → RISK → ORDER → FILL
- **제외 사유/거절 사유 투명 공개** — 왜 이 종목이 거절되었는지 확인 가능

---

## 2. 화면 구성

```
┌─────────────────────────────────────────────────────────┐
│  SAT3 Dashboard                         2026-05-04 14:30 │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ SYSTEM   │ SESSION  │  MARKET  │  RISK    │  PORTFOLIO  │
│ ● HEALTHY│ REGULAR  │  BULL    │  0/5 REJ│  ₩10.5M     │
│ LIVE:OFF │ BUY:OK   │ SCORE:75 │  ACTIVE  │  +₩500K     │
│ EMG:OFF  │ TRADING  │ NEW:OK   │          │  2 POS      │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│                                                         │
│  ┌─ Scanner Candidates ─────────────────────────────┐   │
│  │ Symbol    │ Type          │ In/Ex │ Reason        │   │
│  │ 005930    │ RAPID_SURGE   │  IN   │ -             │   │
│  │ 999999    │ RAPID_SURGE   │  EX   │ ETF_EXCLUDED  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Risk Decisions ─────────────────────────────────┐   │
│  │ ID      │ Symbol │ Side │ Allowed │ Reason       │   │
│  │ rd_001  │ 005930 │ BUY  │ YES     │ APPROVED     │   │
│  │ rd_002  │ 000660 │ BUY  │ NO      │ REGIME_BLOCK │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Audit Timeline [corr_abc] ──────────────────────┐   │
│  │ 09:30  SCAN_STARTED                               │   │
│  │ 09:30  CANDIDATE_DISCOVERED  005930               │   │
│  │ 09:31  QUANT_EVALUATED       005930  PASS  85.0   │   │
│  │ 09:31  STRATEGY_SIGNAL       005930  BUY   0.85   │   │
│  │ 09:31  RISK_APPROVED         005930  BUY          │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/dashboard/summary | 전체 요약 |
| GET | /api/dashboard/system | 시스템 상태 |
| GET | /api/dashboard/session | 세션 상태 |
| GET | /api/dashboard/market-regime | 시장 상태 |
| GET | /api/dashboard/scanner/candidates | 스캐너 후보 |
| GET | /api/dashboard/quant/scores | Quant 점수 |
| GET | /api/dashboard/strategy/signals | 전략 신호 |
| GET | /api/dashboard/risk/decisions | 리스크 판단 |
| GET | /api/dashboard/orders | 주문 현황 |
| GET | /api/dashboard/fills | 체결 현황 |
| GET | /api/dashboard/portfolio | 포트폴리오 |
| GET | /api/dashboard/eod/latest | 최근 EOD 리포트 |
| GET | /api/dashboard/audit/timeline | Audit 타임라인 |
| GET | /api/dashboard/audit/correlation/{id} | 상관 ID별 추적 |

---

## 4. 각 카드/테이블 필드

### SystemStatusCard
- LIVE_TRADING_ENABLED (true/false — false면 붉은 경고)
- Emergency Stop (active/inactive)
- Modules Loaded (true/false)
- Total Tests 통과 수

### SessionStatusCard
- Session State (REGULAR_MARKET / CLOSED_HOLIDAY / ...)
- 신규매수 가능 여부 (BUY_ALLOWED / BUY_BLOCKED)
- 거래일 여부
- 다음 세션 예정

### MarketRegimeCard
- Market Regime (BULL / NEUTRAL / BEAR / UNKNOWN)
- 신규매수 허용 여부
- Total Score (0~100)
- Candidate Score Adjustment

### ScannerCandidatesTable
- Symbol, Name, Scanner Type, Included/Excluded, Excluded Reason

### QuantScoresTable
- Symbol, Scanner Type, Decision (PASS/WATCH/REJECT), Final Score

### RiskDecisionsTable
- RiskDecision ID, Symbol, Side, Allowed, Reason Code, Reason Text

### OrdersTable
- OrderIntent ID, Symbol, Side, Status (SUBMITTED/FAILED/REJECTED_BY_GATE)

### FillsTable
- Fill ID, Order ID, Symbol, Side, Filled Qty, Price, Remaining Qty

### PortfolioTable
- Symbol, Name, Quantity, Avg Buy Price, Current Price, Unrealized PnL

### EodSummaryCard
- Trading Date, Total PnL, Realized/Unrealized, Win Rate, Profit Factor

### AuditTimelineTable
- Timestamp, Event Type, Correlation ID, Symbol, Severity
- correlation_id로 필터링 가능

---

## 5. 실전 주문 버튼 미제공 원칙

Dashboard는 **순수 관제용**이다. 화면에 다음은 절대 포함하지 않는다:
- "매수" / "매도" 버튼
- "주문 실행" / "주문 승인" 버튼
- "Risk 승인" / "강제 승인" 버튼
- "Emergency Stop 해제" 버튼 (표시만)
- 전략 파라미터 직접 수정 필드
- LIVE_TRADING_ENABLED 토글

---

## 6. LIVE_TRADING_ENABLED=false 표시 원칙

- false 상태: 상단에 붉은 배너 "⚠ LIVE TRADING DISABLED — 주문 제출 차단됨"
- true 상태: 녹색 표시 "● LIVE TRADING ENABLED"
- Dashboard는 표시만 하고 값 변경은 절대 하지 않음

---

## 7. Audit Timeline / correlation_id 추적 방식

- Audit Timeline은 시간순으로 모든 Audit Event를 표시
- correlation_id를 클릭하면 해당 거래의 전체 흐름을 필터링하여 표시
- 추적 흐름: SCAN_STARTED → CANDIDATE_DISCOVERED → QUANT_EVALUATED → STRATEGY_SIGNAL_CREATED → RISK_APPROVED/REJECTED → ORDER_INTENT_APPROVED → ORDER_SUBMITTED → FILL_CONFIRMED

---

## 8. 향후 DB/KIS 실제 연결 시 확장 방식

- 현재: InMemory DashboardService → `_candidates`, `_audit_events` 리스트
- DB 연결 후: `DashboardService`가 DB/SQLAlchemy repository를 주입받도록 변경
- KIS 연결 후: SystemStatusView의 `live_trading_enabled`가 실제 .env 값 반영
- session_state, market_regime이 실제 KIS API + 엔진 평가 결과를 반영
- Frontend는 React/Vite 기반 SPA로 구축 (본 문서의 설계를 따름)
