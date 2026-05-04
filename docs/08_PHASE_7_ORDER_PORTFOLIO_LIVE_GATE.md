# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 08. Phase 7 - Live Order Gate + Order/Fill/Portfolio Sync

## 1. Phase 목적

이 Phase의 목표는 Risk Engine을 통과한 신호만 실제 KIS 주문으로 연결하는 Live Order Gate와 주문/체결/포지션 동기화 구조를 만드는 것이다.

```text
핵심 원칙:
- RiskDecision.allowed=true인 경우에만 주문 가능
- Session Guard를 한 번 더 통과해야 주문 가능
- 주문 성공을 체결 성공으로 간주하지 않는다.
- 체결은 KIS 체결조회 또는 실시간 체결통보로 확정한다.
- 포지션은 내부 추정이 아니라 KIS 잔고조회 기준으로 동기화한다.
```

## 2. 작업 범위

생성 권장 구조:

```text
backend/orders/
├─ __init__.py
├─ order_intent.py
├─ order_validator.py
├─ live_order_gate.py
├─ live_order_submitter.py
├─ order_result.py
├─ fill_sync.py
├─ cancel_modify.py
└─ order_state.py

backend/portfolio/
├─ __init__.py
├─ balance_sync.py
├─ position_state.py
├─ pnl_calculator.py
└─ position_snapshot.py

backend/tests/test_order_*.py
backend/tests/test_fill_*.py
backend/tests/test_portfolio_*.py
docs/sat3_live_order_portfolio.md
```

## 3. 금지 사항

```text
금지:
- Risk Engine 우회 주문
- Session Guard 우회 주문
- 주문 성공 = 체결 성공 처리
- fake fill 생성
- fake balance 생성
- virtual portfolio 생성
- KIS 외부 체결/잔고 데이터 사용
- LIVE_TRADING_ENABLED=false 상태에서 주문 제출
- SESSION_STATE_UNKNOWN 상태에서 주문 제출
```

## 4. OrderIntent 모델

RiskDecision이 승인된 뒤에만 생성 가능하다.

```python
@dataclass(frozen=True)
class OrderIntent:
    order_intent_id: str
    risk_decision_id: str
    signal_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: str
    qty: int
    price: int | None
    expected_amount: int
    created_at: datetime
```

규칙:

```text
RiskDecision.allowed=false → OrderIntent 생성 금지
OrderIntent 생성 시 Audit Event ORDER_INTENT_CREATED 기록
```

## 5. Live Order Gate

`live_order_gate.py`는 실제 주문 직전 최종 문이다.

필수 체크:

```text
- RiskDecision.allowed == true
- LIVE_TRADING_ENABLED == true
- Emergency Stop == false
- SessionPolicy.allow_new_buy 또는 allow_sell 확인
- KIS source metadata 확인
- 주문 수량/가격 유효성 확인
- 중복 주문 재확인
```

Live Order Gate 실패 시 주문을 전송하지 않는다.

## 6. Live Order Submitter

`live_order_submitter.py`는 KIS 주문 API를 호출한다.

필수 처리:

```text
- KIS 주문 endpoint 호출
- 요청/응답 correlation_id 연결
- KIS 주문번호 저장
- 응답 코드 저장
- 실패 사유 저장
- 민감정보 마스킹
- ORDER_SUBMITTED 또는 ORDER_FAILED audit event 기록
```

주의:

```text
주문 API 응답이 성공이어도 아직 체결이 아니다.
체결은 Fill Sync에서 별도 확인한다.
```

## 7. Fill Sync

체결 확정은 아래 중 하나를 기준으로 한다.

```text
- KIS 주문체결조회
- KIS 실시간체결통보
```

Fill 모델:

```python
@dataclass(frozen=True)
class FillRecord:
    fill_id: str
    kis_order_no: str
    symbol: str
    side: Literal["BUY", "SELL"]
    filled_qty: int
    filled_price: int
    filled_amount: int
    commission: int | None
    tax: int | None
    fill_time: datetime
    partial_fill: bool
    remaining_qty: int
    source_endpoint: str
```

규칙:

```text
부분체결 허용
미체결 수량 추적
체결 조회 실패 시 체결 추정 금지
체결 확정 시 FILL_CONFIRMED audit event 기록
```

## 8. Cancel / Modify

정정/취소는 명확한 정책 아래 구현한다.

```text
허용:
- 미체결 주문 취소
- 장 마감 전 미체결 정리
- 주문 오류 대응

금지:
- 체결된 주문을 미체결처럼 취소 처리
- KIS 조회 없이 내부 상태만으로 취소 완료 처리
```

## 9. Portfolio Sync

포지션은 KIS 잔고조회 기준으로 동기화한다.

```python
@dataclass(frozen=True)
class PositionSnapshot:
    position_snapshot_id: str
    symbol: str
    symbol_name: str | None
    qty: int
    average_price: int
    current_price: int
    evaluated_amount: int
    unrealized_pnl: int
    realized_pnl: int | None
    pnl_rate: float
    source_endpoint: str
    synced_at: datetime
```

규칙:

```text
KIS 잔고조회 실패 시 포지션 추정 금지
내부 체결 로그와 KIS 잔고가 불일치하면 data_quality_warning 기록
POSITION_SYNCED audit event 기록
```

## 10. Order State

주문 상태는 최소 다음을 구분한다.

```text
CREATED
SUBMITTED
SUBMIT_FAILED
PARTIALLY_FILLED
FILLED
CANCEL_REQUESTED
CANCELLED
MODIFY_REQUESTED
MODIFIED
UNKNOWN
```

`UNKNOWN` 상태에서는 신규 추가 주문을 보수적으로 제한할 수 있어야 한다.

## 11. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_order_intent.py
backend/tests/test_live_order_gate.py
backend/tests/test_live_order_submitter.py
backend/tests/test_fill_sync.py
backend/tests/test_portfolio_sync.py
```

필수 테스트:

```text
1. RiskDecision.allowed=false이면 OrderIntent 생성 금지
2. LIVE_TRADING_ENABLED=false이면 주문 제출 금지
3. Session State가 주문 허용 상태가 아니면 제출 금지
4. Emergency Stop이면 제출 금지
5. 주문 성공 응답이 체결로 기록되지 않음
6. KIS 체결조회 결과가 있어야 FillRecord 생성
7. 부분체결 처리
8. 체결조회 실패 시 fake fill 생성 금지
9. KIS 잔고조회 결과로 PositionSnapshot 생성
10. 잔고조회 실패 시 포지션 추정 금지
11. ORDER_SUBMITTED/ORDER_FAILED/FILL_CONFIRMED/POSITION_SYNCED audit event 생성
12. secret/account full value가 로그에 없음
```

## 12. 문서 산출물

```text
docs/sat3_live_order_portfolio.md
```

포함 내용:

```text
- Live Order Gate 원칙
- OrderIntent 모델
- 주문 제출 조건
- 주문 성공과 체결 확정의 차이
- Fill Sync 구조
- Partial Fill 처리
- Portfolio Sync 구조
- 주문 상태 모델
- Audit Log payload
- Dashboard 주문/체결/포지션 화면 요구사항
```

## 13. 검증 명령

```bash
pytest backend/tests/test_order_intent.py backend/tests/test_live_order_gate.py backend/tests/test_live_order_submitter.py backend/tests/test_fill_sync.py backend/tests/test_portfolio_sync.py
git diff -- backend/orders backend/portfolio backend/tests docs/sat3_live_order_portfolio.md
git status --short
```

## 14. Hermes 보고 형식

```text
Phase 7 완료 보고

1. 생성/수정 파일:
2. OrderIntent 구조:
3. Live Order Gate 체크 목록:
4. 주문 성공/체결 확정 분리 방식:
5. Fill Sync 구조:
6. Portfolio Sync 구조:
7. Audit Event 연결:
8. 테스트 결과:
9. 금지 영역 변경 여부:
10. git diff 요약:
11. git status:
12. 커밋 여부: 미수행
```
