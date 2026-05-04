# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 03. Phase 2 - Trading Session / Market Schedule Engine

## 1. Phase 목적

SAT3는 실전 자동매매 프로그램이므로 주식시장 개장일, 휴장일, 개장시간, 폐장시간, 장운영 상태에 맞춰 자동으로 동작해야 한다.

이 Phase의 목표는 **시장 일정과 장운영 상태에 따라 자동매매 가능 여부를 제어하는 엔진**을 만드는 것이다.

```text
핵심 원칙:
- 로컬 PC 시간만 믿고 주문하지 않는다.
- KIS 국내휴장일조회와 장운영정보를 기준으로 판단한다.
- 휴장일에는 자동매매를 실행하지 않는다.
- 장전/장후/동시호가/마감 임박 구간에서는 신규매수를 차단한다.
- 정규장 중에만 신규매수를 허용한다.
- 장 상태를 알 수 없으면 주문하지 않는다.
```

## 2. 작업 범위

생성 권장 구조:

```text
backend/session/
├─ __init__.py
├─ trading_calendar.py
├─ session_state.py
├─ market_clock.py
├─ session_policy.py
├─ session_scheduler.py
├─ session_guard.py
└─ session_events.py

backend/tests/test_session_*.py
docs/sat3_trading_session_engine.md
```

## 3. 금지 사항

```text
금지:
- 실제 주문 실행 코드 수정
- 전략 조건 수정
- 스캐너 조건 수정
- 모의투자 기능 추가
- 로컬 시간만으로 주문 허용
- KIS API 조회 실패 시 임의로 장중 처리
- 휴장일 자동매매 허용
- SESSION_STATE_UNKNOWN 상태에서 주문 허용
```

## 4. Session State 모델

아래 상태를 enum으로 정의한다.

```text
CLOSED_HOLIDAY
- 휴장일
- 자동매매 미실행

CLOSED_BEFORE_MARKET
- 거래일이지만 장 시작 전
- 점검/동기화 가능
- 신규매수 금지

PRE_MARKET_AUCTION
- 장전 동시호가/예상체결
- 관찰 가능
- 신규매수 금지

REGULAR_MARKET
- 정규장
- 조건 충족 시 신규매수 가능

LATE_MARKET
- 장 마감 임박
- 신규매수 금지
- 보유 종목 관리 중심

CLOSING_AUCTION
- 장마감 동시호가
- 신규매수 금지
- 정책에 따라 청산만 허용 가능

AFTER_MARKET
- 장후 시간외
- 기본 자동매매 금지
- 체결/잔고 동기화 가능

CLOSED_AFTER_MARKET
- 장 종료 후
- EOD 리포트 가능
- 신규 주문 금지

SESSION_STATE_UNKNOWN
- API 실패 또는 상태 불명
- 신규 주문 차단
```

## 5. 상태별 정책

`session_policy.py`는 상태별 허용 작업을 반환한다.

필수 필드:

```python
@dataclass(frozen=True)
class SessionPolicy:
    session_state: TradingSessionState
    allow_scan: bool
    allow_new_buy: bool
    allow_sell: bool
    allow_cancel: bool
    allow_sync: bool
    allow_eod: bool
    reason: str
```

정책 예시:

```text
CLOSED_HOLIDAY:
- scan=false
- new_buy=false
- sell=false
- cancel=false
- sync=true
- eod=false

REGULAR_MARKET:
- scan=true
- new_buy=true
- sell=true
- cancel=true
- sync=true
- eod=false

LATE_MARKET:
- scan=false 또는 제한
- new_buy=false
- sell=true
- cancel=true
- sync=true
- eod=false

CLOSED_AFTER_MARKET:
- scan=false
- new_buy=false
- sell=false
- cancel=false
- sync=true
- eod=true

SESSION_STATE_UNKNOWN:
- 모든 신규 주문 금지
```

## 6. Trading Calendar

`trading_calendar.py` 역할:

```text
- 오늘이 거래일인지 확인
- 휴장일 여부 확인
- 다음 거래일 계산
- KIS 국내휴장일조회 API 사용
- API 실패 시 DataUnavailable 처리
```

주의:

```text
휴장일 판단은 로컬 달력으로만 하지 않는다.
KIS API 조회 실패 시 휴장/개장 추정 금지.
상태 불명이면 주문 차단.
```

## 7. Market Clock

`market_clock.py` 역할:

```text
- KIS 장운영정보 조회
- 현재 장 상태 계산
- 로컬 시간과 KIS 장상태 불일치 감지
- 상태 전환 이벤트 생성
```

필수 결과 객체:

```python
@dataclass(frozen=True)
class MarketSessionSnapshot:
    trading_day: bool
    session_state: TradingSessionState
    kis_market_status: str | None
    local_time: datetime
    api_checked_at: datetime | None
    source_endpoints: tuple[str, ...]
    reason: str
```

## 8. Session Guard

`session_guard.py`는 주문 전 최종 세션 검증에 사용된다.

신규매수 허용 조건:

```text
- 오늘이 거래일
- session_state == REGULAR_MARKET
- policy.allow_new_buy == true
- SESSION_STATE_UNKNOWN 아님
- LATE_MARKET 아님
- CLOSED_HOLIDAY 아님
```

거절 코드:

```text
SESSION_CLOSED_HOLIDAY
SESSION_BEFORE_MARKET
SESSION_PRE_MARKET_AUCTION
SESSION_LATE_MARKET_BUY_BLOCKED
SESSION_CLOSING_AUCTION
SESSION_AFTER_MARKET
SESSION_CLOSED_AFTER_MARKET
SESSION_STATE_UNKNOWN
SESSION_API_UNAVAILABLE
```

## 9. 서버 재시작 복구 정책

문서와 코드 주석에 아래 순서를 포함한다.

```text
서버 시작 시:
1. KIS 토큰 상태 확인
2. 국내휴장일조회
3. 장운영정보 조회
4. 현재 session_state 계산
5. LIVE_TRADING_ENABLED 확인
6. Emergency Stop 확인
7. KIS 잔고 동기화
8. 미체결 주문 조회
9. 보유 종목 동기화
10. 현재 세션 정책에 맞는 작업만 재개
```

이 Phase에서는 실제 동기화 구현은 하지 않아도 된다.  
단, 이후 Portfolio/Order Phase에서 호출할 수 있도록 interface를 정의한다.

## 10. Audit Event 연결 준비

Phase 3 Logging Engine에서 사용할 event type을 정의해둔다.

```text
TRADING_DAY_CHECKED
MARKET_SESSION_EVALUATED
SESSION_STATE_CHANGED
PRE_MARKET_STARTED
REGULAR_MARKET_STARTED
LATE_MARKET_STARTED
NEW_BUY_BLOCKED_BY_SESSION
MARKET_CLOSED
AFTER_MARKET_SYNC_STARTED
EOD_TRIGGERED_BY_SESSION
SESSION_STATE_UNKNOWN
```

## 11. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_session_state.py
backend/tests/test_session_policy.py
backend/tests/test_session_guard.py
backend/tests/test_trading_calendar.py
```

필수 테스트:

```text
1. CLOSED_HOLIDAY에서는 신규매수 금지
2. CLOSED_BEFORE_MARKET에서는 신규매수 금지
3. PRE_MARKET_AUCTION에서는 신규매수 금지
4. REGULAR_MARKET에서만 신규매수 허용
5. LATE_MARKET에서는 신규매수 금지
6. AFTER_MARKET에서는 신규매수 금지
7. SESSION_STATE_UNKNOWN에서는 신규 주문 금지
8. KIS 휴장일 조회 실패 시 주문 금지
9. 로컬 시간이 장중이어도 KIS 상태 불명이면 주문 금지
10. EOD는 CLOSED_AFTER_MARKET에서만 허용
```

## 12. 문서 산출물

```text
docs/sat3_trading_session_engine.md
```

포함 내용:

```text
- Session State 정의
- 상태별 정책
- KIS API 기준 판단 원칙
- 로컬 시간 단독 판단 금지
- Session Guard 구조
- 서버 재시작 복구 정책
- Dashboard 표시 요구사항
- Audit Event 목록
```

## 13. 검증 명령

```bash
pytest backend/tests/test_session_state.py backend/tests/test_session_policy.py backend/tests/test_session_guard.py backend/tests/test_trading_calendar.py
git diff -- backend/session backend/tests docs/sat3_trading_session_engine.md
git status --short
```

## 14. Hermes 보고 형식

```text
Phase 2 완료 보고

1. 생성/수정 파일:
2. Session State 정의:
3. 상태별 정책 요약:
4. Session Guard 거절 코드:
5. KIS API 실패 시 처리:
6. 서버 재시작 복구 정책:
7. 테스트 결과:
8. 금지 영역 변경 여부:
9. git diff 요약:
10. git status:
11. 커밋 여부: 미수행
```
