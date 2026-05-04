# StockAutoTrader V3 (SAT3)

> 실전 자동매매 운영 플랫폼 — 한국투자증권 Open API 단일 출처, 정량평가 중심, 급등주 단타 전략

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