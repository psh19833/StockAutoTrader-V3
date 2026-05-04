# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 04. Phase 3 - Audit / Logging Engine

## 1. Phase 목적

SAT3의 로그는 단순 디버깅용이 아니다.  
실전 자동매매의 **블랙박스**, 즉 판단 근거와 사고 추적 자료다.

이 Phase의 목표는 모든 핵심 이벤트를 `correlation_id`로 추적 가능한 구조로 저장하는 Audit / Logging Engine을 만드는 것이다.

```text
로그 설계 목적:
- 실전 주문 사고 추적
- 스캔 후보 선정 근거 보존
- 정량평가 점수 근거 보존
- 전략 신호 발생 근거 보존
- 리스크 승인/거절 근거 보존
- 주문/체결 상태 추적
- 장 종료 후 성과 분석과 전략 개선 자료화
```

## 2. 작업 범위

생성 권장 구조:

```text
backend/logging/
├─ __init__.py
├─ logger.py
├─ audit_event.py
├─ audit_writer.py
├─ log_sanitizer.py
├─ correlation.py
├─ schemas.py
└─ retention.py

backend/tests/test_audit_*.py
docs/sat3_audit_logging_engine.md
```

주의: Python 표준 `logging` 모듈과 이름 충돌이 생기면 `backend/audit/` 또는 `backend/audit_logging/`으로 변경해도 된다.

## 3. 금지 사항

```text
금지:
- 민감정보 로그 출력
- 주문 성공을 체결 성공으로 기록
- API 실패 시 추정값 생성 로그
- fake fill / fake balance / simulated order 이벤트 추가
- 운영 코드에 secret/token/account full value 저장
- .env 내용 로그화
```

## 4. 로그 계층

SAT3 로그는 3계층으로 나눈다.

```text
1. Application Log
- 사람이 보는 서버 로그
- 콘솔/파일
- INFO/WARNING/ERROR

2. Audit Event Log
- 시스템 판단 근거 로그
- DB 또는 파일 저장 가능
- 검색/분석 가능
- event_type 기반

3. Raw API Log
- KIS API 원본 응답 또는 해시
- 민감정보 마스킹 필수
- 장기 보관 시 hash 중심
```

## 5. Audit Event 스키마

필수 모델:

```python
@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    event_time: datetime
    severity: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    correlation_id: str | None
    trading_day: date | None
    symbol: str | None
    strategy_name: str | None
    payload: dict[str, Any]
    source: str
```

## 6. Event Type 목록

최소한 아래 event_type을 정의한다.

```text
SERVER_STARTED
SERVER_STOPPED
CONFIG_LOADED
CONFIG_INVALID

KIS_API_CALLED
KIS_API_FAILED
KIS_API_DATA_UNAVAILABLE
KIS_TOKEN_REFRESHED

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

MARKET_REGIME_EVALUATED

SCAN_STARTED
SCAN_COMPLETED
CANDIDATE_DISCOVERED
CANDIDATE_EXCLUDED

QUANT_EVALUATED

STRATEGY_SIGNAL_CREATED

RISK_APPROVED
RISK_REJECTED

ORDER_INTENT_CREATED
ORDER_SUBMITTED
ORDER_FAILED
ORDER_CANCELLED
ORDER_MODIFIED

FILL_CONFIRMED
PARTIAL_FILL_CONFIRMED

POSITION_SYNCED

EOD_REPORT_CREATED
EOD_REPORT_FAILED

EMERGENCY_STOP_ACTIVATED
EMERGENCY_STOP_RELEASED
LIVE_TRADING_ENABLED_CHANGED
```

## 7. Correlation ID

하나의 거래 흐름은 같은 correlation_id로 이어져야 한다.

```text
스캔
↓
정량평가
↓
전략 신호
↓
리스크 검증
↓
주문
↓
체결
↓
포지션 반영
↓
EOD 리포트
```

예시:

```text
TRADE-20260504-091203-005930-breakout
SCAN-20260504-090501
REGIME-20260504-090000
```

`correlation.py`에는 다음 기능이 필요하다.

```text
- scan_run_id 생성
- evaluation_id 생성
- signal_id 생성
- risk_decision_id 생성
- order_intent_id 생성
- trade correlation_id 생성
```

## 8. Log Sanitizer

어떤 로그에도 아래 값이 노출되면 안 된다.

```text
- KIS app key
- KIS app secret
- access token
- refresh token
- approval key
- 계좌번호 전체
- 텔레그램 bot token
- 텔레그램 chat_id 전체
- API header 원문
- .env 전체 내용
```

마스킹 규칙 예시:

```text
12345678-01 → 1234****-**
abcdef1234567890 → abcd********7890
```

`log_sanitizer.py`는 dict, list, string 모두 재귀적으로 sanitizing할 수 있어야 한다.

## 9. Audit Writer

`audit_writer.py`는 초기에는 파일 기반 JSONL로 구현해도 된다.

권장 저장 경로:

```text
data/audit/events/YYYY-MM-DD.jsonl
```

이후 DB 저장으로 확장 가능해야 한다.

필수 기능:

```text
- append_event
- append_many
- sanitize before write
- JSON serializable 변환
- write failure 시 application log 기록
```

## 10. 각 로그에 들어갈 주요 payload

### 10.1 KIS API Log

```text
endpoint
tr_id
request_id
success
http_status
kis_error_code
latency_ms
retry_count
raw_response_hash
parsed_result_count
```

### 10.2 Scanning Log

```text
scan_run_id
scan_type
source_endpoints
collected_count
deduped_count
excluded_count
final_candidate_count
included_reason
excluded_reason
```

### 10.3 Quant Evaluation Log

```text
evaluation_id
scan_run_id
symbol
base_candidate_score
adjusted_candidate_score
market_adjustment
component_scores
symbol_risk_penalty
final_decision
reasons
source_endpoints
stale_data
missing_data
```

### 10.4 Risk Decision Log

```text
risk_decision_id
signal_id
allowed
reason_code
reason_text
checked_items
failed_items
market_regime_check
session_check
daily_loss_limit_check
duplicate_order_check
reentry_block_check
stale_data_check
live_trading_enabled_check
emergency_stop_check
```

### 10.5 Order / Fill Log

```text
order_intent_id
risk_decision_id
kis_order_no
symbol
side
order_type
qty
price
submit_result
kis_response_code
kis_message
order_status

fill_id
kis_order_no
filled_qty
filled_price
filled_amount
commission
tax
fill_time
partial_fill
remaining_qty
source_endpoint
```

## 11. 보관 정책

문서에 다음 정책을 포함한다.

```text
Application Log:
- 30일 보관
- 날짜별 rotation

Audit Event Log:
- 최소 1년 보관
- 검색 가능

Raw API Log:
- 7~30일 보관
- 민감정보 마스킹
- 장기 보관은 hash 중심

EOD Summary:
- 장기 보관
```

## 12. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_audit_event.py
backend/tests/test_log_sanitizer.py
backend/tests/test_correlation.py
backend/tests/test_audit_writer.py
```

필수 테스트:

```text
1. AuditEvent 생성 가능
2. event_type 누락 시 실패
3. correlation_id 생성 형식 검증
4. dict/list/string의 민감정보 마스킹
5. token/app_secret/account full value가 output에 없는지 검증
6. JSONL writer가 event를 저장하는지
7. payload 안의 datetime/date가 직렬화되는지
8. fake fill / simulated order event type이 정의되지 않았는지
```

## 13. 문서 산출물

```text
docs/sat3_audit_logging_engine.md
```

포함 내용:

```text
- 로그 목적
- 로그 계층
- AuditEvent 스키마
- EventType 목록
- Correlation ID 정책
- Secret Masking 정책
- 보관 정책
- Dashboard 로그 화면 요구사항
```

## 14. 검증 명령

```bash
pytest backend/tests/test_audit_event.py backend/tests/test_log_sanitizer.py backend/tests/test_correlation.py backend/tests/test_audit_writer.py
git diff -- backend/logging backend/tests docs/sat3_audit_logging_engine.md
git status --short
```

## 15. Hermes 보고 형식

```text
Phase 3 완료 보고

1. 생성/수정 파일:
2. AuditEvent 스키마:
3. EventType 목록:
4. Correlation ID 정책:
5. Secret Masking 테스트 결과:
6. 저장 방식:
7. 테스트 결과:
8. 금지 영역 변경 여부:
9. git diff 요약:
10. git status:
11. 커밋 여부: 미수행
```
