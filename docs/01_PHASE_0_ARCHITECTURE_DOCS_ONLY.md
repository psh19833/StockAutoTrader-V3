# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 01. Phase 0 - SAT3 설계 문서화 및 SAT2 구조 분석

## 1. Phase 목적

이 Phase는 **코드를 개발하지 않고**, SAT3 개발을 시작하기 위한 설계 문서와 SAT2 구조 분석 문서를 만드는 단계다.

가장 중요한 목표는 다음이다.

```text
- SAT2 구조를 읽고 자동매매 핵심 모듈을 분류한다.
- SAT3 최상위 원칙을 문서화한다.
- 모의투자/가짜데이터/시뮬레이션 요소를 찾아 목록화한다.
- KIS API 외부 데이터 출처가 있는지 찾아 목록화한다.
- SAT3 목표 아키텍처와 Phase별 개발 순서를 확정한다.
```

## 2. 작업 범위

허용되는 작업은 문서 생성과 구조 분석뿐이다.

```text
허용:
- 프로젝트 파일 구조 읽기
- grep/ripgrep으로 키워드 검색
- 문서 파일 생성
- docs/ 하위 md 문서 작성
- 현재 구조 분석
- 위험 영역 목록화

금지:
- Python/JS/TS 코드 수정
- 주문 로직 수정
- 브로커/KIS API 호출부 수정
- 전략 조건 수정
- .env 수정
- 서버 실행
- 자동매매 실행
- 실제 주문 실행
- 커밋
```

## 3. 반드시 검색할 키워드

SAT2 안에 아래 개념이 남아 있는지 검색한다.

```text
mock
paper
simulation
simulated
virtual
fake
dummy
demo
sandbox
test broker
fake fill
fake balance
virtual balance
sample stock
generated symbol
random price
synthetic
fallback price
fallback data
```

한국투자증권 API 외부 데이터 출처도 검색한다.

```text
requests.get
httpx.get
BeautifulSoup
selenium
naver
daum
finance
csv
pandas.read_csv
manual symbols
hardcoded symbols
```

주의: 검색 결과가 테스트 코드에만 있다면 별도로 구분해서 보고한다.

## 4. 생성할 문서

아래 문서 하나를 생성한다.

```text
docs/sat3_upgrade_plan.md
```

문서에는 다음 내용이 포함되어야 한다.

```text
1. SAT3 최상위 정의
2. SAT3 절대 원칙
3. 모의투자 완전 제거 정책
4. READ_ONLY_MODE와 모의투자의 차이
5. KIS API 단일 출처 정책
6. API 조회 실패 시 처리 정책
7. Market Schedule / Trading Session Engine 개요
8. Market Regime Engine 개요
9. Quant Candidate Evaluation 개요
10. Scanner / Strategy / Risk / Order 역할 분리
11. Audit / Logging Engine 개요
12. EOD Daily Performance Report 개요
13. 단계별 개발 Phase
14. SAT2에서 발견된 위험 요소
15. 테스트 전략 초안
16. 금지 영역 목록
```

## 5. SAT3 최상위 원칙 문구

문서에 아래 문구를 반드시 포함한다.

```text
SAT3는 실전 자동매매 전용 시스템이다.
SAT3에는 모의투자, 가상투자, simulated broker, fake fill, virtual balance 개념을 넣지 않는다.
단, 실전 사고 방지를 위한 READ_ONLY_MODE 또는 LIVE_TRADING_ENABLED=false 주문 차단 안전장치는 허용한다.
READ_ONLY_MODE는 KIS API의 실제 데이터를 조회하되 실제 주문 전송만 차단하는 안전장치이며, 모의투자가 아니다.
```

## 6. KIS API 단일 출처 정책 문구

문서에 아래 문구를 반드시 포함한다.

```text
SAT3의 모든 시장 데이터, 종목 정보, 계좌 정보, 주문 정보, 체결 정보는 한국투자증권 Open API에서만 가져온다.
API 조회 실패 시 시스템은 추정값을 생성하지 않는다.
조회 실패 데이터는 DataUnavailable 또는 평가 불가 상태로 처리한다.
KIS 외부 출처, 크롤링, 수동 CSV, 임의 가격, 임의 종목정보, 임의 잔고, 임의 체결은 금지한다.
```

## 7. SAT3 목표 흐름

문서에 아래 흐름을 반드시 포함한다.

```text
KIS API Gateway
↓
Trading Calendar / Session Engine
↓
Market Data Service
↓
Market Regime Engine
↓
Scanner Engine
↓
Quant Candidate Evaluation
↓
Market Regime Score Adjustment
↓
Strategy Engine
↓
Risk Engine
↓
Trading Session Guard
↓
Live Order Gate
↓
KIS Live Order Submitter
↓
Fill Sync
↓
Portfolio Sync
↓
Audit Log / EOD Report
```

## 8. 테스트 전략 초안

Phase 0에서는 테스트 코드를 작성하지 않아도 된다.  
단, 문서에는 이후 Phase별 테스트 방향을 작성해야 한다.

```text
- KIS Source Policy 테스트
- Session State 판단 테스트
- Secret Masking 테스트
- Market Regime Score 계산 테스트
- Scanner 후보 수집/제외 테스트
- Quant Score 계산 테스트
- Risk Decision 승인/거절 테스트
- Order Gate 주문 차단 테스트
- Fill Sync 체결 확정 테스트
- EOD Report 집계 테스트
```

## 9. 검증 명령

작업 후 반드시 확인한다.

```bash
git diff -- docs/sat3_upgrade_plan.md
git status --short
```

문서 외 변경이 있으면 원복한다.

## 10. Hermes 보고 형식

```text
Phase 0 완료 보고

1. 생성 문서:
- docs/sat3_upgrade_plan.md

2. 현재 SAT2 구조 분석 요약:
- backend 주요 모듈:
- frontend 주요 모듈:
- reports 주요 모듈:
- trading/order 관련 모듈:

3. 발견된 모의투자/가짜데이터 관련 요소:
- 운영 코드:
- 테스트 코드:
- 문서:

4. 발견된 KIS 외부 데이터 출처:
- 운영 코드:
- 테스트 코드:
- 문서:

5. SAT3 설계 요약:
- 실전 전용:
- KIS API 단일 출처:
- Market Regime:
- Quant Evaluation:
- Logging:
- EOD Report:

6. 위험 영역:
- 주문 관련:
- 계좌/잔고 관련:
- 전략 관련:
- API 관련:

7. git diff 요약:

8. git status:

9. 커밋 여부:
- 커밋하지 않음
```
