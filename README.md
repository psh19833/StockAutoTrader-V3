# StockAutoTrader V3 (SAT3)

> 실전 자동매매 운영 플랫폼 — 한국투자증권 Open API 단일 출처, 정량평가 중심, 급등주 단타 전략

## 안전 보강 상태 (중요)
- 본 프로젝트는 Dashboard / Telegram / Audit / 운영 문서 / SafetyGate 골격을 구축 중입니다.
- 현재 시점에서 "실전 자동매매(LIVE)"는 live runner / KIS order submitter가 안전 보강 Phase로 분리되어 있으며, 기본 동작은 dry-run(합성/예시) 파이프라인입니다.
- LIVE_TRADING_ENABLED=true 설정만으로 실전 주문이 실행되면 안 됩니다.
- --confirm-live-order가 있어도 live runner가 NOT_READY/BLOCKED 상태이면 자동매매 시작(주문 제출)은 금지됩니다.

### 실전 주문 가능(예정) 조건
아래가 모두 충족되어야만 실전 주문 submit이 가능해야 합니다(현재 Phase에서는 미구현/차단).
- 실제 KIS order submitter 구현 및 주입
- LiveTradingRunner 준비(Scanner/Quant/Strategy/Risk/SafetyGate 연결 포함)
- SafetyGate 통과
- LIVE_TRADING_ENABLED=true 수동 설정
- --confirm-live-order 명시

## 원칙

- **실전 계좌 전용** — 모의투자/가상 잔고/시뮬레이션 없음
- **KIS API 단일 출처** — 외부 크롤링/CSV/수동 데이터 금지
- **정량평가 중심** — Market Regime → Scanner → Quant → Strategy → Risk Engine 순의 엄격한 파이프라인
- **로그 증거화** — 모든 판단과 주문이 `correlation_id` 기반 Audit Log로 추적
- **TDD 개발** — 각 Phase를 테스트 주도로 개발

## Phase 목록

| Phase | 내용 | 상태 |
|-------|------|------|
| 0 | 설계 문서화 및 SAT2 구조 분석 | ✅ 진행 중 |
| 1 | KIS API Gateway | ⬜ |
| 2 | Market Data Layer | ⬜ |
| 3 | Market Regime + Scanner | ⬜ |
| 4 | Quant Evaluation Engine | ⬜ |
| 5 | Strategy Layer | ⬜ |
| 6 | Risk Engine | ⬜ |
| 7 | Order Gate + Execution | ⬜ |
| 8 | Reporting + Monitoring | ⬜ |
| 9 | Integration + Hardening | ⬜ |

## 프로젝트 구조

```
StockAutoTrader-V3/
├── docs/                 # 설계 문서
│   └── sat3_upgrade_plan.md  # SAT2→SAT3 업그레이드 계획
├── backend/              # Python 백엔드 (개발 예정)
├── .env                  # 환경 변수 (KIS API 키)
└── README.md             # 이 파일
```

## 시작하기

1. Python 3.12+ 가상환경 생성
2. `pip install -r requirements.txt`
3. `.env` 파일 설정 (KIS API 키/계좌번호)
4. Phase 1부터 순차적으로 개발 진행