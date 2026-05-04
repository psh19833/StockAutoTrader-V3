# SAT3 Upgrade Plan

> 이 문서는 SAT2(StockAutoTrader V2)의 구조 분석 결과와 SAT3(StockAutoTrader V3)로의 업그레이드 계획을 정의합니다.
> 생성일: 2026-05-04
> 최종 수정: Phase 4 완료 시점 반영

---

## 1. SAT2 구조 분석

### 1.1 프로젝트 구조 개요

```text
StockAutoTrader-V2/
├── backend/
│   ├── analysis/         # 후보 검토, 리스크 위원회, 거래 일지
│   ├── api/              # FastAPI 엔드포인트
│   ├── broker/           # 브로커 인터페이스 (KIS + Mock)
│   ├── core/             # 이벤트 버스, 스키마
│   ├── database/         # DB 연결 및 모델
│   ├── engine/           # 봇 러너, 엔진
│   ├── mcp_tools/        # MCP 서버 및 도구
│   ├── operations/       # 자동 오케스트레이터
│   ├── order/            # 주문 관리자
│   ├── replay/           # 리플레이 시스템
│   ├── reports/          # EOD 보고서, 텔레그램
│   ├── risk/             # 리스크 관리
│   ├── scanner/          # 스캐너
│   ├── services/         # DB 로그, 텔레그램 서비스
│   ├── strategy/         # 전략 (기본 + 앙상블)
│   ├── scripts/          # 유틸리티 스크립트
│   ├── tests/            # 테스트
│   ├── main.py           # 진입점
│   ├── config.py         # 설정
│   ├── market_data.py    # 시장 데이터
│   ├── market_hours.py   # 장시간
│   ├── bootstrap.py      # 부트스트랩
│   └── runtime_context.py# 런타임 컨텍스트
├── frontend/             # React/Vite 프론트엔드
├── docs/                 # 문서
└── tools/                # 도구
```

### 1.2 핵심 모듈 분류

| 모듈 | 역할 | SAT3 이관 여부 |
|------|------|---------------|
| broker/kis_broker.py | KIS API 호출 | 재사용 (단순화) |
| broker/base.py | 브로커 추상 기본 클래스 | 재설계 |
| broker/mock_broker.py | Mock 브로커 **(제거 대상)** | **완전 제거** |
| order/order_manager.py | 주문 관리 | 신규 설계 |
| engine/engine.py | 매매 엔진 | 신규 설계 |
| scanner/ | 스캐너 | 신규 설계 |
| strategy/ | 전략 | 신규 설계 |
| risk/risk_manager.py | 리스크 관리 | 신규 설계 |
| replay/ | 리플레이 | 불필요 (SAT3 미포함) |
| reports/ | 보고서/텔레그램 | 단순화 |
| api/ | REST API | 단순화 |

---

## 2. SAT2 위험 요소 분석

### 2.1 발견된 Mock/Simulation 코드

#### 💥 치명적: `backend/broker/mock_broker.py` (202 lines)

**파일:** `/home/psh19/StockAutoTrader-V2/backend/broker/mock_broker.py`

SAT3로 이관 시 **반드시 제거**해야 하는 파일입니다. 주요 포함 내용:

- `MockBroker` 클래스: BrokerBase 상속, 가상 계좌/포지션/주가 반환
- `_MOCK_ACCOUNT`: 가상 계좌 정보 (1,000만원 자산)
- `_MOCK_POSITIONS`: 가상 보유 종목 (삼성전자 10주)
- `_MOCK_STOCK_PRICES`: 5개 종목의 가상 시세
- `place_buy_order() / place_sell_order()`: 모든 주문을 "FILLED"로 즉시 체결
- `get_price()`: 알 수 없는 종목은 `random.randint()`로 무작위 가격 생성
- `is_mock = True` 속성

#### 🟡 위험: `backend/config.py` — 모의투자 관련 설정

**파일:** `/home/psh19/StockAutoTrader-V2/backend/config.py`

- `BROKER_MODE` 기본값이 `"MOCK"` (환경변수 미설정 시 모의 브로커)
- `KIS_IS_MOCK` 환경변수 없으면 기본 `True` (모의투자)
- `load_config()`에서 강제로 `KIS_IS_MOCK = False`로 오버라이드하지만, 코드 자체가 모의투자 분기를 포함

→ SAT3에서는 `KIS_IS_MOCK`, `BROKER_MODE=MOCK`, `KIS_BASE_URL_MOCK` 등 모든 모의투자 관련 변수를 **완전 제거**

#### 🟡 위험: `backend/broker/kis_broker.py` — 모의/실전 분기 코드

**파일:** `/home/psh19/StockAutoTrader-V2/backend/broker/kis_broker.py`

- `config.KIS_IS_MOCK` 기반으로 실전 URL / 모의 URL 분기 (line 27)
- `config.KIS_IS_MOCK` 기반으로 TR ID (모의/실전) 분기 (line 31)
- `broker_name`에 `"Mock"` / `"Real"` 모드 표시
- `is_mock` 속성 반환

→ SAT3에서는 모의투자 URL/TR ID 코드를 제거하고 실전 전용으로 고정

### 2.2 모듈별 Mock 관련 검색 결과

| 모듈 | 검색어 | 결과 |
|------|--------|------|
| broker/mock_broker.py | mock, virtual, fake, dummy | **발견 (위 2.1 참조)** |
| broker/kis_broker.py | is_mock, KIS_IS_MOCK | **발견 (모의/실전 분기)** |
| config.py | MOCK, KIS_IS_MOCK | **발견 (기본값 MOCK)** |
| engine/*.py | mock, simulation | 없음 |
| order/*.py | mock, simulation | 없음 |
| risk/*.py | mock, simulation | 없음 |
| scanner/*.py | mock, simulation | 없음 |
| strategy/*.py | mock, simulation | 없음 |
| api/*.py | mock, simulation | 없음 |
| tests/*.py | mock (테스트용) | 테스트 전용이므로 SAT3에는 불필요 |

### 2.3 외부 데이터 출처 분석

SAT2는 Phase 0 검색 기준:
- `requests.get()` / `httpx.get()` 직접 호출: **발견되지 않음** (KIS API는 broker 레이어로 캡슐화)
- `BeautifulSoup` / `selenium` / `naver` / `daum`: **발견되지 않음**
- `pandas.read_csv()`: **발견되지 않음**
- 하드코딩된 종목 심볼: **발견되지 않음**

→ SAT2는 KIS API 단일 출처 원칙을 대체로 잘 지키고 있음.

---

## 3. SAT3 설계 방향

### 3.1 절대 원칙

```text
1. 한국투자증권 Open API 단일 출처
2. 실전 계좌 전용 (모의투자/가상 잔고 없음)
3. 정량평가 중심 종목 선정
4. Market Regime → Scanner → Quant → Strategy → Risk Engine 순의 엄격한 파이프라인
5. 모든 판단과 주문이 로그로 추적되는 Audit 시스템
6. ETF/ETN/ELW/REIT/SPAC/인버스/레버리지/UNKNOWN 상품 제외, KOSPI/KOSDAQ 보통주만 매매
7. 급등주 단타 우선 + 시장상태 기반 멀티 스캐너 (RAPID_SURGE, LIQUIDITY_MOMENTUM, BREAKOUT, PULLBACK_REBOUND)
8. 실전 주문 전 리스크 엔진 필수 통과
9. 급등주라는 이유로 Risk Engine 우회 또는 손절 기준 완화 금지
10. 상품 유형을 알 수 없으면 절대 통과시키지 않음
```

### 3.2 SAT2에서 가져올 것

- `broker/kis_broker.py` — KIS API 인증/호출 로직 (단순화하여 재사용)
- `config.py` — 환경 변수 설정 패턴
- `database/` — DB 연결 및 모델 (단순화)
- `market_hours.py` — 장시간 계산 로직
- Telegram 전송 유틸리티 (reports/telegram_*.py)

### 3.3 SAT2에서 제거할 것

- `broker/mock_broker.py` — **Mock 브로커 완전 제거** (실전 전용)
- 모든 `is_mock` / `READ_ONLY_MODE` / `LIVE_TRADING_ENABLED` 관련 코드
- `replay/` 시스템 — SAT3 구조와 불일치
- 복잡한 프론트엔드 — 가능하면 단순 CLI 기반

### 3.4 SAT3 현재 아키텍처 (Phase 4 완료 기준)

```text
backend/
├─ kis/                          # Phase 1 — KIS API Gateway
│  ├─ client.py
│  ├─ auth.py
│  ├─ endpoints.py
│  ├─ rate_limit.py
│  ├─ errors.py
│  ├─ schemas.py
│  ├─ raw_logger.py
│  └─ source_policy.py
│
├─ session/                      # Phase 2 — Trading Session Engine
│  ├─ trading_calendar.py
│  ├─ session_state.py
│  ├─ market_clock.py
│  ├─ session_policy.py
│  ├─ session_scheduler.py
│  ├─ session_guard.py
│  └─ session_events.py
│
├─ audit_logging/                # Phase 3 — Audit Logging Engine
│  ├─ audit_event.py             #   27종 AuditEventType
│  ├─ audit_writer.py            #   InMemoryAuditWriter
│  ├─ log_sanitizer.py           #   Secret masking
│  ├─ correlation.py
│  ├─ retention.py
│  └─ logger.py
│
├─ notifications/                # Phase 3B — Telegram Event Notification
│  ├─ telegram_event.py          #   20종 TelegramEventType
│  ├─ telegram_formatter.py      #   AuditEvent → Telegram 메시지
│  ├─ telegram_policy.py         #   Allowlist/blocklist/throttling
│  ├─ telegram_sender.py         #   InMemoryTelegramSender
│  └─ telegram_notifier.py       #   Policy → Formatter → Sender
│
├─ market_regime/                # Phase 4 — Market Regime Engine
│  ├─ regime_state.py            #   BULL/NEUTRAL/BEAR/UNKNOWN
│  ├─ regime_score.py            #   7개 세부 점수 + Risk Penalty
│  ├─ regime_result.py
│  ├─ regime_inputs.py           #   KIS_API source 검증
│  ├─ regime_policy.py           #   분류 + 정책 결정
│  ├─ regime_calculator.py       #   8개 계산 함수
│  └─ regime_audit.py            #   → MARKET_REGIME_EVALUATED
│
├─ scanner/                      # Phase 5 — Scanner (예정)
│  ├─ scanner_types.py
│  ├─ candidate.py
│  ├─ exclusion_reasons.py
│  ├─ common_filters.py
│  ├─ scanner_engine.py
│  ├─ rapid_surge_scanner.py
│  ├─ liquidity_momentum_scanner.py
│  ├─ breakout_scanner.py
│  ├─ pullback_rebound_scanner.py
│  └─ scan_audit.py
│
├─ quant/                        # Phase 5 — Quant Evaluation (예정)
│  ├─ candidate_score.py
│  ├─ score_components.py
│  ├─ scoring_config.py
│  ├─ rapid_surge_score.py
│  ├─ pullback_score.py
│  ├─ market_adjustment.py
│  ├─ quant_evaluator.py
│  └─ quant_audit.py
│
├─ strategies/                   # Phase 6 — Strategy Engine (예정)
├─ risk/                         # Phase 6 — Risk Engine (예정)
├─ orders/                       # Phase 7 — Order Gate (예정)
├─ portfolio/                    # Phase 7 — Portfolio Sync (예정)
├─ reports/                      # Phase 8 — EOD Report (예정)
│
├─ tests/
│  ├─ test_kis_*.py              # Phase 1 (128 tests)
│  ├─ test_session_*.py          # Phase 2 (88 tests)
│  ├─ test_audit_logging.py     # Phase 3 (56 tests)
│  ├─ test_telegram_notification.py # Phase 3B (47 tests)
│  ├─ test_market_regime.py      # Phase 4 (54 tests)
│  ├─ test_scanner_*.py          # Phase 5 (예정)
│  └─ test_quant_*.py            # Phase 5 (예정)
│
└─ docs/
   ├─ 00_SAT3_MASTER_PLAN.md
   ├─ 01_PHASE_0_*.md
   ├─ ...
   ├─ 05_PHASE_4_MARKET_REGIME_ENGINE.md
   ├─ 06_PHASE_5_SCANNER_QUANT_ENGINE.md
   ├─ 06B_PHASE_5B_RAPID_SURGE_SCANNER_STRATEGY_POLICY.md
   └─ 07_PHASE_6_STRATEGY_RISK_ENGINE.md (예정)
```

---

## 4. Phase별 개발 순서 (완료 현황 반영)

| Phase | 내용 | 상태 |
|-------|------|------|
| 0 | 설계 문서화 및 SAT2 구조 분석 | ✅ 완료 |
| 1 | KIS API Gateway + Source Policy | ✅ 완료 (`7a451d3`) |
| 2 | Trading Session / Market Schedule Engine | ✅ 완료 (`c794fb0`) |
| 3 | Audit / Logging Engine | ✅ 완료 (`04351bb`) |
| 3B | Telegram Event Notification Engine | ✅ 완료 (`37690a5`) |
| 4 | Market Regime Engine | ✅ 완료 (`9d2a9e2`) |
| 5 | KOSPI/KOSDAQ Common Stock Scanner + Quant Candidate Evaluation | 🔲 예정 |
| 5B | KOSPI/KOSDAQ Multi-Scanner + Rapid Surge Strategy Policy | 🔲 예정 (문서화 완료) |
| 6 | Strategy Engine + Risk Engine | 🔲 예정 |
| 6B | Fast Exit / Stop Loss 정책 | 🔲 예정 |
| 7 | Live Order Gate + Order/Fill/Portfolio Sync | 🔲 예정 |
| 8 | EOD Daily Performance Report + Dashboard Adapter | 🔲 예정 |
| 9 | Integration Hardening + 안전성 검증 + 릴리즈 준비 | 🔲 예정 |

---

## 5. SAT3 매매 Universe 정책 (Phase 5B 기준)

### 5.1 매매 허용

```text
- KOSPI common stock
- KOSDAQ common stock
```

### 5.2 매매 제외

```text
- ETF
- ETN
- ELW
- REIT
- SPAC
- preferred stock / 우선주
- warrant / 신주인수권
- inverse product
- leveraged product
- management issue
- investment warning/caution/risk issue
- trading halt issue
- delisting/administrative issue
- product_type UNKNOWN
- KOSPI/KOSDAQ 외 시장
```

### 5.3 중요 원칙

```text
- 상품 유형을 알 수 없으면 제외한다.
- KOSPI/KOSDAQ 여부를 확인할 수 없으면 제외한다.
- KIS API source metadata 없이 종목명/패턴으로 허용 판단하지 않는다.
- Scanner PASS는 매수 신호가 아니다.
- Quant PASS도 매수 신호가 아니다.
급등주라는 이유로 Risk Engine을 우회하거나 손절 기준을 완화하지 않는다.
```

---

## 6. SAT3 Scanner 정책 (Phase 5B 기준)

Scanner는 단순 수집기가 아니라 **정량 조건 기반 후보 발굴기**다.

### 6.1 Scanner 역할

```text
- KIS API Gateway를 통해 후보 데이터 수집
- KOSPI/KOSDAQ 보통주만 유지
- 제외 상품을 정량/메타데이터 기준으로 제거
- scanner_type별 정량 조건 적용
- 조건 통과한 종목만 ScannerCandidate로 생성
- 후보 편입 사유와 탈락 사유 모두 기록
- 모든 metric과 source_endpoint 기록
```

### 6.2 Scanner 금지

```text
- 매수 신호 생성
- 매도 신호 생성
- 주문 수량 계산
- 손절/익절가 확정
- Risk Engine 역할 수행
- 주문 허용 여부 판단
```

### 6.3 Scanner Type 및 Market Regime별 활성 정책

| Scanner Type | 목적 | BULL | NEUTRAL | BEAR | UNKNOWN |
|---|---|---|---|---|---|
| **RAPID_SURGE** | 급등 초기 후보 포착 | 적극 허용 | 고득점만 허용 | 비활성/강한 감점 | 차단 |
| **LIQUIDITY_MOMENTUM** | 안정적 상승 모멘텀 (승률 보완) | 유지 | 중심 | 비활성/감점 | 차단 |
| **BREAKOUT** | 당일 고점/전고점 돌파 | 적극 허용 | 제한적 허용 | 비활성 | 차단 |
| **PULLBACK_REBOUND** | 눌림 후 재상승 (추격 위험 완화) | 유지 | 중심 | 비활성/감점 | 차단 |

---

## 7. SAT3 점수 파이프라인

```text
Market Regime Score (100점 기준)
  ↓  BULL: +7.5 adjustment
  ↓  NEUTRAL: 0 adjustment
  ↓  BEAR/UNKNOWN: new buy blocked, -20~-30 adjustment
  ↓

Scanner → 정량 조건 필터링 → ScannerCandidate
  ↓

Quant Candidate Score (Base + Scanner Specific - Risk Penalty)
  = Liquidity + Spread + Volume + Momentum + Trend + Orderbook
  + Volatility Safety
  + RAPID_SURGE 전용: surge_velocity, volume_burst, high_proximity, vi_proximity
  + PULLBACK_REBOUND 전용: prior_strength, pullback_depth, rebound, support
  - Symbol Risk Penalty
  + Market Regime Adjustment
  ↓

Strategy Engine (Phase 6)
  ↓  시장 상태 + 후보 점수 → 매수/매도 신호

Risk Engine (Phase 6)
  ↓  리스크 승인/기각

Session Guard (Phase 2)
  ↓  장 상태 확인

Order Gate (Phase 7)
  ↓  실제 주문 전송
```

---

## 8. Market Regime 정책 요약 (Phase 4)

| 상태 | 점수 | Adjustment | Allow New Buy | Min Score | Risk Penalty 연동 |
|---|---|---|---|---|---|
| **BULL** | 70~100 | +7.5 | ✅ | 50 | penalty≥25 → NEUTRAL downgrade |
| **NEUTRAL** | 40~69 | 0 | ✅ | 50 | penalty≥25 → BEAR downgrade |
| **BEAR** | 0~39 | -20 | ❌ | 999 | penalty≥35 → 차단 |
| **UNKNOWN** | N/A | -30 | ❌ | 999 | 데이터 부족 시 |

---

## 9. 빠른 청산 정책 방향 (Phase 6 구현 예정)

```text
- 고정 손절: -1.0% ~ -2.0%
- 1차 익절: +1.0% ~ +2.0%
- 트레일링 스탑: 고점 대비 -0.5% ~ -1.2%
- 시간 손절: 진입 후 10~30분 내 상승 실패 시 정리
- 급락 감지 청산
- 체결강도 약화 청산
- 호가 매도벽/스프레드 악화 청산
- 장 마감 전 청산 정책
```

**주의:** 불장이라고 손절폭을 넓히지 않음. 급등주라는 이유로 손절 기준 완화 금지.

---

## 10. Audit / Telegram 연결 요약

### Audit Event Type (27종, Phase 3)

```text
SERVER_STARTED, SERVER_STOPPED
KIS_API_CALLED, KIS_API_FAILED
TRADING_DAY_CHECKED, MARKET_SESSION_EVALUATED, SESSION_STATE_CHANGED
NEW_BUY_BLOCKED_BY_SESSION, SESSION_STATE_UNKNOWN
MARKET_REGIME_EVALUATED
SCAN_STARTED, SCAN_COMPLETED, CANDIDATE_DISCOVERED, CANDIDATE_EXCLUDED
QUANT_EVALUATED
STRATEGY_SIGNAL_CREATED
RISK_APPROVED, RISK_REJECTED
ORDER_INTENT_APPROVED, ORDER_SUBMITTED, ORDER_FAILED, ORDER_CANCELLED
FILL_CONFIRMED, POSITION_SYNCED
EOD_REPORT_CREATED
EMERGENCY_STOP_ACTIVATED, EMERGENCY_STOP_RELEASED
```

### Telegram Notification (20종, Phase 3B)

```text
SERVER_STARTED .. EOD_REPORT_CREATED .. KIS_API_FAILED 포함 20종
ORDER_SUBMITTED와 FILL_CONFIRMED는 구분되어 전송
secret masking 적용
실패해도 매매 흐름 중단 없음 (safe failure)
```

---

## 11. 핵심 위험 경고

```text
⚠️ MockBroker (backend/broker/mock_broker.py)는 SAT3로 절대 이관 금지
⚠️ KIS API 인증 정보는 .env로만 관리, 하드코딩 금지
⚠️ Phase 7 이전에는 주문 관련 코드 일체 금지
⚠️ TDD 방식으로 각 Phase를 독립적으로 개발
⚠️ 각 Phase 완료 시 11항목 보고서 필수
⚠️ ETF/ETN/ELW/REIT/SPAC/UNKNOWN 상품은 어떤 fallback도 허용하지 않음
⚠️ 급등주라는 이유로 Risk Engine 우회 금지 (Phase 5B 정책)
⚠️ KIS API source metadata 없이 종목명 패턴만으로 허용 판단 금지
⚠️ 상품 유형 UNKNOWN인 종목은 절대 후보로 통과시키지 않음
```