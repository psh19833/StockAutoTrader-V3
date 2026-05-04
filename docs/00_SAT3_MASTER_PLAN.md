# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 00. SAT3 전체 개발 마스터 플랜

## 1. SAT3 최상위 정의

SAT3는 SAT2의 단순 기능 추가 버전이 아니다.  
SAT3는 다음 조건을 만족하는 **실전 자동매매 운영 플랫폼**이다.

```text
SAT3 =
한국투자증권 Open API 단일 출처 기반
실전 계좌 전용
모의투자 없는 자동매매 시스템
정량평가 중심 종목 선정
시장 상태 선평가 기반 매매 제어
실전 주문 전 리스크 엔진 필수 통과
모든 판단과 주문이 로그로 추적되는 운영 플랫폼
```

## 2. SAT3 절대 원칙

### 2.1 모의투자 완전 제거

SAT3에는 아래 개념을 넣지 않는다.

```text
금지:
- paper trading
- mock trading
- simulated broker
- fake fill
- virtual balance
- virtual portfolio
- demo mode
- sandbox order
- fake price
- generated symbol
- synthetic market data
- 임의 종목정보 생성
- 임의 잔고 생성
- 임의 체결 생성
```

허용되는 것은 **주문 차단 안전장치**뿐이다.

```text
허용:
- READ_ONLY_MODE
- LIVE_TRADING_ENABLED=false
- Emergency Stop
- 주문 전송 직전 차단
```

주의: READ_ONLY_MODE는 모의투자가 아니다.  
KIS API의 실제 데이터를 조회하고 평가하되, 실제 주문 전송만 차단하는 안전장치다.

### 2.2 한국투자증권 Open API 단일 출처

모든 시장 데이터, 종목 정보, 계좌 정보, 주문 정보, 체결 정보는 한국투자증권 Open API에서만 가져온다.

```text
허용:
- KIS API 응답 저장
- KIS API 응답 정규화
- KIS API 응답 기반 점수 계산
- KIS API 응답 기반 리스크 판단
- KIS API 호출 실패 로그

금지:
- 네이버/다음/구글 금융 크롤링
- 수동 CSV 종목 리스트
- 임의 종목명/종목코드 생성
- API 실패 시 추정값 보정
- 가격/거래량/잔고/체결 임의 생성
```

### 2.3 정량평가 중심

SAT3는 “감”으로 종목을 선정하지 않는다.

모든 후보 종목은 다음 단계를 거친다.

```text
Market Regime 평가
↓
Scanner 후보 수집
↓
Quant Candidate Evaluation
↓
Market Regime 보정
↓
Strategy Signal
↓
Risk Engine
↓
Trading Session Guard
↓
Live Order Gate
↓
KIS 실제 주문
```

### 2.4 로그 없는 판단 금지

```text
로그 없는 스캔은 스캔으로 인정하지 않는다.
로그 없는 정량평가는 평가로 인정하지 않는다.
로그 없는 전략 신호는 주문 후보가 될 수 없다.
로그 없는 리스크 승인은 주문으로 이어질 수 없다.
로그 없는 체결은 체결로 인정하지 않는다.
```

## 3. SAT3 목표 아키텍처

```text
backend/
├─ kis/
│  ├─ client.py
│  ├─ auth.py
│  ├─ endpoints.py
│  ├─ rate_limit.py
│  ├─ errors.py
│  ├─ schemas.py
│  ├─ raw_logger.py
│  └─ source_policy.py
│
├─ session/
│  ├─ trading_calendar.py
│  ├─ session_state.py
│  ├─ market_clock.py
│  ├─ session_policy.py
│  ├─ session_scheduler.py
│  ├─ session_guard.py
│  └─ session_events.py
│
├─ logging/
│  ├─ logger.py
│  ├─ audit_event.py
│  ├─ audit_writer.py
│  ├─ log_sanitizer.py
│  ├─ correlation.py
│  ├─ schemas.py
│  └─ retention.py
│
├─ market/
│  ├─ market_data_service.py
│  ├─ market_regime.py
│  ├─ index_trend.py
│  ├─ market_breadth.py
│  ├─ market_momentum.py
│  ├─ market_volatility.py
│  ├─ trading_value.py
│  └─ sector_strength.py
│
├─ scanner/
│  ├─ scanner_engine.py
│  ├─ ranking_collectors.py
│  ├─ candidate.py
│  ├─ exclusion_filters.py
│  └─ scan_log_adapter.py
│
├─ quant/
│  ├─ candidate_score.py
│  ├─ liquidity.py
│  ├─ momentum.py
│  ├─ volume.py
│  ├─ orderbook.py
│  ├─ trend.py
│  ├─ fundamental.py
│  ├─ risk_penalty.py
│  ├─ scoring_config.py
│  └─ explanation.py
│
├─ strategies/
│  ├─ base.py
│  ├─ registry.py
│  ├─ breakout_strategy.py
│  ├─ pullback_strategy.py
│  └─ volume_surge_strategy.py
│
├─ risk/
│  ├─ risk_engine.py
│  ├─ risk_decision.py
│  ├─ checks.py
│  ├─ limits.py
│  └─ rejection_codes.py
│
├─ orders/
│  ├─ order_intent.py
│  ├─ order_validator.py
│  ├─ live_order_submitter.py
│  ├─ fill_sync.py
│  ├─ cancel_modify.py
│  └─ order_state.py
│
├─ portfolio/
│  ├─ balance_sync.py
│  ├─ position_state.py
│  ├─ pnl_calculator.py
│  └─ position_snapshot.py
│
└─ reports/
   ├─ eod_performance_report.py
   ├─ eod_report_builder.py
   ├─ eod_report_storage.py
   ├─ eod_telegram_formatter.py
   └─ eod_dashboard_adapter.py
```

## 4. 개발 Phase 목록

SAT3는 한 번에 개발하지 않는다.  
아래 순서대로 **각 Phase를 별도 작업 단위로 진행**한다.

```text
Phase 0  : SAT3 설계 문서화 및 SAT2 구조 분석
Phase 1  : KIS API Gateway + Source Policy
Phase 2  : Trading Session / Market Schedule Engine
Phase 3  : Audit / Logging Engine
Phase 4  : Market Regime Engine
Phase 5  : Scanner + Quant Candidate Evaluation
Phase 6  : Strategy Engine + Risk Engine
Phase 7  : Live Order Gate + Order/Fill/Portfolio Sync
Phase 8  : EOD Daily Performance Report + Dashboard Adapter
Phase 9  : Integration Hardening + 안전성 검증 + 릴리즈 준비
```

## 5. 진행 원칙

각 Phase마다 반드시 지켜야 한다.

```text
1. 한 Phase에서 지정된 범위 외 파일을 수정하지 않는다.
2. 주문 관련 코드는 지정된 Phase 전까지 수정하지 않는다.
3. .env 파일을 수정하지 않는다.
4. secret/token/account full value를 로그에 남기지 않는다.
5. KIS 외부 데이터 출처를 추가하지 않는다.
6. 모의투자/가짜체결/가짜잔고 구조를 추가하지 않는다.
7. 테스트를 먼저 또는 함께 작성한다.
8. git diff와 git status를 반드시 보고한다.
9. 커밋은 사용자가 지시하기 전까지 하지 않는다.
```

## 6. Hermes 공통 보고 형식

각 Phase 완료 후 Hermes는 아래 형식으로 보고한다.

```text
1. 작업 Phase
2. 변경 파일 목록
3. 생성 파일 목록
4. 수정 파일 목록
5. 금지 영역 변경 여부
6. 테스트 결과
7. 주요 설계 결정
8. 남은 리스크
9. git diff 요약
10. git status
11. 커밋 여부: 미수행
```

## 7. SAT3 성공 기준

```text
- 휴장일에는 자동매매가 시작되지 않는다.
- 장 상태를 알 수 없으면 주문하지 않는다.
- 베어장에서는 신규매수가 제한 또는 차단된다.
- 모든 종목 평가는 KIS API 데이터에 근거한다.
- 모든 주문은 Risk Engine과 Session Guard를 통과해야 한다.
- 주문 성공을 체결 성공으로 간주하지 않는다.
- 체결은 KIS 체결조회 또는 실시간 체결통보로 확정한다.
- EOD 리포트에서 승률/수익률/전략별 성과/시장 상태별 성과를 확인할 수 있다.
- 모든 주요 판단은 correlation_id로 추적 가능하다.
```

---

## 다음에 Hermes에게 줄 문서

첫 개발 시작 시에는 반드시 아래 파일부터 전달한다.

```text
01_PHASE_0_ARCHITECTURE_DOCS_ONLY.md
```
