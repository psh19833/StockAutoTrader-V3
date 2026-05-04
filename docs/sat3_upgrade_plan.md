# SAT3 Upgrade Plan

> 이 문서는 SAT2(StockAutoTrader V2)의 구조 분석 결과와 SAT3(StockAutoTrader V3)로의 업그레이드 계획을 정의합니다.
> 생성일: 2026-05-04

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
6. ETF/ETN/파생형 상품 제외
7. 급등주 단타 전략 중심
8. 실전 주문 전 리스크 엔진 필수 통과
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

### 3.4 SAT3 목표 아키텍처

```text
┌─────────────────────────────────────────────┐
│                 CLI / MCP                    │
├─────────────────────────────────────────────┤
│      Market Regime → Scanner → Quant        │
│      → Strategy → Risk Engine → Order Gate  │
├─────────────────────────────────────────────┤
│            KIS API Gateway                   │
├─────────────────────────────────────────────┤
│         Database (SQLite/PostgreSQL)         │
├─────────────────────────────────────────────┤
│         Audit Log System                     │
└─────────────────────────────────────────────┘
```

---

## 4. Phase별 개발 순서

| Phase | 내용 | 범위 |
|-------|------|------|
| 0 | 설계 문서화 및 SAT2 구조 분석 | **현재 진행 중** |
| 1 | KIS API Gateway 구현 | kis_client, 인증, 토큰 갱신 |
| 2 | Market Data Layer | 실시간/히스토리 데이터 |
| 3 | Market Regime + Scanner | 시장 상태 평가, 종목 스캔 |
| 4 | Quant Evaluation Engine | 정량 평가 점수 계산 |
| 5 | Strategy Layer | 매매 전략 신호 생성 |
| 6 | Risk Engine | 리스크 평가, 주문 차단 |
| 7 | Order Gate + Execution | 주문 전송, 체결 관리 |
| 8 | Reporting + Monitoring | 로그, 보고서, 알림 |
| 9 | Integration + Hardening | 통합 테스트, 안정화 |

---

## 5. 핵심 위험 경고

```text
⚠️ MockBroker (backend/broker/mock_broker.py)는 SAT3로 절대 이관 금지
⚠️ KIS API 인증 정보는 .env로만 관리, 하드코딩 금지
⚠️ Phase 7 이전에는 주문 관련 코드 일체 금지
⚠️ TDD 방식으로 각 Phase를 독립적으로 개발
⚠️ 각 Phase 완료 시 11항목 보고서 필수
```