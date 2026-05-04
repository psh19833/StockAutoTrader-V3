# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 10. Phase 9 - Integration Hardening + 안전성 검증 + 릴리즈 준비

## 1. Phase 목적

이 Phase는 SAT3를 실제 운용 가능한 수준으로 묶기 위한 통합 안정화 단계다.

```text
목표:
- Phase 1~8 모듈 연결
- 실전 주문 안전 경로 최종 검증
- 모의투자/가짜데이터 혼입 여부 재검사
- KIS API 단일 출처 위반 여부 재검사
- 로그/리포트/대시보드 흐름 검증
- 서버 재시작 복구 흐름 검증
- 소액 실전 운용 전 최종 체크리스트 작성
```

## 2. 작업 범위

허용 범위:

```text
- 모듈 간 interface 연결
- API router 연결
- Dashboard read-only 화면 연결
- 설정 validation 강화
- 통합 테스트 추가
- 문서 보완
- 안전 체크리스트 작성
```

주의: 이 Phase에서도 실제 대량 매매 실행은 금지한다.

## 3. 금지 사항

```text
금지:
- 안전장치 없이 LIVE_TRADING_ENABLED 기본값 true
- Emergency Stop 제거
- Risk Engine 우회
- Session Guard 우회
- KIS 외부 데이터 추가
- 모의투자/가짜체결 재도입
- 테스트 없이 주문 관련 변경
- .env에 secret 직접 커밋
```

## 4. 통합 흐름 검증

최종 흐름:

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

## 5. 안전 기본값

운영 설정 기본값은 보수적으로 둔다.

```text
LIVE_TRADING_ENABLED=false
READ_ONLY_MODE=true 또는 주문 차단 상태
Emergency Stop 기본 활성 가능
최대 보유 종목 수 낮게
종목당 최대 투자금 낮게
일일 최대 손실 한도 낮게
Bear 시장 신규매수 차단
SESSION_STATE_UNKNOWN 주문 차단
KIS API 실패 주문 차단
```

## 6. 설정 검증

서버 시작 시 설정 검증이 필요하다.

검증 항목:

```text
- KIS app key 존재 여부
- KIS app secret 존재 여부
- 계좌번호 존재 여부
- token 설정 유효성
- LIVE_TRADING_ENABLED 값 명시 여부
- Emergency Stop 상태
- Risk Limits 유효성
- Telegram 설정 유효성
- 로그 저장 경로 쓰기 가능 여부
```

주의:

```text
설정값을 로그로 원문 출력하지 않는다.
존재 여부와 masked value만 표시한다.
```

## 7. API Router / Dashboard 연결

Read-only API 예시:

```text
GET /api/sat3/session/status
GET /api/sat3/market-regime/latest
GET /api/sat3/scanner/latest
GET /api/sat3/quant/candidates
GET /api/sat3/risk/rejections
GET /api/sat3/orders/live
GET /api/sat3/positions
GET /api/sat3/reports/eod/latest
GET /api/sat3/audit/events
```

주의:

```text
Write API는 최소화한다.
주문 실행 API는 별도 강한 confirmation이 필요하다.
대시보드에서 Emergency Stop은 허용 가능하되, 해제는 더 강한 확인이 필요하다.
```

## 8. 통합 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_sat3_integration_read_only.py
backend/tests/test_sat3_live_order_safety.py
backend/tests/test_sat3_source_policy_integration.py
backend/tests/test_sat3_session_market_risk_flow.py
backend/tests/test_sat3_eod_integration.py
```

필수 테스트:

```text
1. LIVE_TRADING_ENABLED=false이면 주문 전송 없음
2. SESSION_STATE_UNKNOWN이면 주문 전송 없음
3. CLOSED_HOLIDAY이면 주문 전송 없음
4. Bear market allow_new_buy=false이면 신규매수 없음
5. RiskDecision.allowed=false이면 OrderIntent 생성 없음
6. KIS source 없는 데이터는 평가/주문 거절
7. stale data이면 주문 거절
8. 주문 성공을 체결로 기록하지 않음
9. KIS 체결조회 결과가 있어야 Fill 생성
10. EOD 리포트는 최종 동기화 후 생성
11. secret/token/account full value가 로그/리포트/API 응답에 없음
12. correlation_id로 scan→evaluation→signal→risk→order→fill 추적 가능
```

## 9. 금지 키워드 재검사

최종 통합 전 아래 키워드를 재검색한다.

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
fake fill
fake balance
virtual balance
synthetic
random price
generated symbol
fallback price
fallback data
```

결과는 아래로 분류한다.

```text
- 운영 코드에 존재: 위험
- 테스트 fixture에 존재: 허용 가능
- 문서에 존재: 설명 목적이면 허용
```

## 10. KIS 외부 출처 재검사

```text
naver
daum
BeautifulSoup
selenium
requests.get
httpx.get
pandas.read_csv
csv
manual symbol
hardcoded symbols
```

운영 코드에서 KIS 외부 금융 데이터 출처가 발견되면 반드시 제거 또는 격리한다.

## 11. 운영 리허설 절차

실전 주문 없이 READ_ONLY 상태로 하루 운용하는 절차를 문서화한다.

```text
1. 서버 시작
2. KIS token 확인
3. 휴장일/장운영정보 확인
4. Session State 확인
5. Market Regime 평가
6. Scanner 실행
7. Quant 평가
8. Strategy Signal 생성 여부 확인
9. Risk Engine 거절/승인 로그 확인
10. LIVE_TRADING_ENABLED=false로 주문 차단 확인
11. 장 종료 후 EOD 리포트 생성 확인
12. Telegram 요약 확인
13. Dashboard 데이터 확인
```

주의: 이것은 모의투자가 아니다.  
실제 KIS 데이터를 사용하고, 주문 전송만 차단하는 안전 리허설이다.

## 12. 소액 실전 전환 체크리스트

문서로 작성한다.

```text
- 모든 테스트 통과
- 금지 키워드 운영 코드 미검출
- KIS 외부 데이터 출처 미검출
- secret 로그 노출 테스트 통과
- LIVE_TRADING_ENABLED 기본값 false 확인
- Emergency Stop 동작 확인
- Session Guard 동작 확인
- Risk Engine 거절 로그 확인
- 주문 실패 처리 확인
- Fill Sync 확인
- EOD Report 확인
- Telegram 알림 확인
- Dashboard 상태 확인
- 종목당 최대 투자금 소액 설정
- 일일 손실 한도 소액 설정
```

## 13. 문서 산출물

```text
docs/sat3_integration_hardening.md
docs/sat3_release_checklist.md
docs/sat3_read_only_rehearsal.md
```

## 14. 검증 명령

```bash
pytest
git grep -n "mock\|paper\|simulation\|simulated\|virtual\|fake\|dummy\|sandbox\|synthetic" -- backend frontend docs
git grep -n "naver\|daum\|BeautifulSoup\|selenium\|pandas.read_csv\|manual symbol\|hardcoded" -- backend frontend docs
git diff
git status --short
```

## 15. Hermes 보고 형식

```text
Phase 9 완료 보고

1. 생성/수정 파일:
2. 통합 연결 요약:
3. 안전 기본값:
4. API/Dashboard 연결:
5. 통합 테스트 결과:
6. 금지 키워드 검사 결과:
7. KIS 외부 출처 검사 결과:
8. READ_ONLY 리허설 절차:
9. 소액 실전 전환 체크리스트:
10. 남은 리스크:
11. git diff 요약:
12. git status:
13. 커밋 여부: 미수행
```
