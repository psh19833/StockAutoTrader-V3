# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 07. Phase 6 - Strategy Engine + Risk Engine

## 1. Phase 목적

이 Phase의 목표는 정량평가 결과를 바탕으로 전략 신호를 만들고, 실전 주문 전 반드시 통과해야 하는 Risk Engine을 구축하는 것이다.

```text
핵심 원칙:
- Strategy Signal은 주문이 아니다.
- Risk Engine 승인 없이는 주문 Intent도 만들 수 없다.
- Risk Engine은 실전 주문 전 최종 방어막이다.
- 시장 상태, 세션 상태, 계좌 상태, 데이터 출처, stale 여부를 모두 검증한다.
```

## 2. 작업 범위

생성 권장 구조:

```text
backend/strategies/
├─ __init__.py
├─ base.py
├─ registry.py
├─ signal.py
├─ breakout_strategy.py
├─ pullback_strategy.py
└─ volume_surge_strategy.py

backend/risk/
├─ __init__.py
├─ risk_engine.py
├─ risk_decision.py
├─ checks.py
├─ limits.py
├─ rejection_codes.py
└─ risk_log_adapter.py

backend/tests/test_strategy_*.py
backend/tests/test_risk_*.py
docs/sat3_strategy_risk_engine.md
```

## 3. 금지 사항

```text
금지:
- 실제 주문 전송
- KIS 주문 API 호출
- fake broker 사용
- 모의 체결 생성
- Risk Engine 우회
- LIVE_TRADING_ENABLED=false 상태에서 주문 허용
- SESSION_STATE_UNKNOWN 상태에서 주문 허용
- Market Regime allow_new_buy=false 상태에서 신규매수 허용
```

## 4. Strategy Engine 역할

Strategy는 `QuantScoreResult`를 입력받아 `SignalIntent`를 생성한다.

```text
Strategy가 하는 일:
- 진입/청산 조건 평가
- signal confidence 계산
- 예상 진입가/손절가/익절가 제안
- 판단 근거 생성
- source_endpoints 전달

Strategy가 하지 않는 일:
- 주문 전송
- 계좌 잔고 최종 판단
- 장 상태 최종 판단
- 리스크 승인
```

## 5. SignalIntent 모델

```python
@dataclass(frozen=True)
class SignalIntent:
    signal_id: str
    evaluation_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    strategy_name: str
    confidence: float
    expected_entry_price: int | None
    stop_loss_price: int | None
    take_profit_price: int | None
    trailing_stop_config: dict[str, Any] | None
    signal_reason: str
    evidence: tuple[str, ...]
    source_endpoints: tuple[str, ...]
    created_at: datetime
```

규칙:

```text
- BUY 신호는 Quant decision이 PASS인 경우에만 생성 가능
- WATCH/REJECT 후보는 BUY Signal 생성 금지
- SELL 신호는 보유 포지션 기반으로 생성
- expected_entry_price가 KIS source 없는 데이터면 거절
```

## 6. Strategy Registry

전략은 플러그인 방식으로 관리한다.

```python
class BaseStrategy(Protocol):
    name: str
    enabled: bool

    def evaluate_entry(...)-> SignalIntent | None:
        ...

    def evaluate_exit(...)-> SignalIntent | None:
        ...
```

전략 enable/disable은 설정으로 관리하되, 이 Phase에서는 기본 구조만 만든다.

## 7. Risk Engine 역할

Risk Engine은 SignalIntent를 받아 주문 허용 여부를 판단한다.

필수 체크:

```text
- LIVE_TRADING_ENABLED 확인
- Emergency Stop 확인
- Session Guard 확인
- Market Regime allow_new_buy 확인
- KIS source metadata 확인
- stale data 여부 확인
- 계좌 잔고/매수가능금액 확인
- 종목당 최대 투자금 확인
- 최대 보유 종목 수 확인
- 동일 종목 보유 여부 확인
- 동일 종목 미체결 주문 여부 확인
- 당일 손절 종목 재진입 제한
- 일일 최대 손실 제한
- 주문 수량/금액 유효성 확인
```

## 8. RiskDecision 모델

```python
@dataclass(frozen=True)
class RiskDecision:
    risk_decision_id: str
    signal_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    requested_qty: int
    requested_amount: int
    allowed: bool
    reason_code: str
    reason_text: str
    checked_items: tuple[str, ...]
    failed_items: tuple[str, ...]
    decided_at: datetime
```

## 9. 거절 코드

최소 거절 코드:

```text
LIVE_TRADING_DISABLED
EMERGENCY_STOP_ACTIVE
SESSION_CLOSED_HOLIDAY
SESSION_BEFORE_MARKET
SESSION_PRE_MARKET_AUCTION
SESSION_LATE_MARKET_BUY_BLOCKED
SESSION_AFTER_MARKET
SESSION_STATE_UNKNOWN
MARKET_REGIME_BLOCKED
DATA_SOURCE_INVALID
STALE_DATA_BLOCKED
DATA_UNAVAILABLE
INSUFFICIENT_CASH
POSITION_LIMIT_EXCEEDED
DUPLICATE_ORDER_BLOCKED
DUPLICATE_POSITION_BLOCKED
REENTRY_BLOCKED
DAILY_LOSS_LIMIT_EXCEEDED
ORDER_AMOUNT_INVALID
ORDER_QTY_INVALID
```

## 10. Risk Limits

`limits.py`에 설정 가능한 제한값 모델을 만든다.

```python
@dataclass(frozen=True)
class RiskLimits:
    max_position_count: int
    max_amount_per_symbol: int
    max_daily_loss_amount: int
    max_daily_loss_rate: float
    reentry_block_minutes: int
    min_candidate_score_for_buy: float
```

기본값은 안전하게 보수적으로 둔다.  
실제 값은 운영 설정에서 주입 가능하게 한다.

## 11. Audit Log 연결

Strategy:

```text
STRATEGY_SIGNAL_CREATED
```

Risk:

```text
RISK_APPROVED
RISK_REJECTED
```

Risk payload에는 반드시 다음을 포함한다.

```text
- checked_items
- failed_items
- reason_code
- reason_text
- market_regime_check
- session_check
- stale_data_check
- live_trading_enabled_check
- emergency_stop_check
```

## 12. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_strategy_signal.py
backend/tests/test_strategy_registry.py
backend/tests/test_risk_engine_approval.py
backend/tests/test_risk_engine_rejection.py
backend/tests/test_risk_session_market_checks.py
```

필수 테스트:

```text
1. REJECT 후보는 BUY Signal 생성 금지
2. PASS 후보는 조건 충족 시 SignalIntent 생성
3. Strategy Signal은 주문을 실행하지 않음
4. LIVE_TRADING_ENABLED=false이면 RiskDecision.allowed=false
5. Emergency Stop이면 allowed=false
6. Session State가 REGULAR_MARKET 아니면 신규매수 거절
7. Market Regime allow_new_buy=false이면 신규매수 거절
8. stale data이면 거절
9. KIS source metadata 없으면 거절
10. 중복 주문/중복 포지션 거절
11. 일일 손실 한도 초과 시 거절
12. RISK_APPROVED/RISK_REJECTED audit event 생성
```

## 13. 문서 산출물

```text
docs/sat3_strategy_risk_engine.md
```

포함 내용:

```text
- Strategy와 Order 분리 원칙
- SignalIntent 모델
- Strategy Registry 구조
- Risk Engine 체크 목록
- RiskDecision 모델
- 거절 코드
- Risk Limits
- Audit Log payload
- Dashboard 리스크 거절 보드 요구사항
```

## 14. 검증 명령

```bash
pytest backend/tests/test_strategy_signal.py backend/tests/test_strategy_registry.py backend/tests/test_risk_engine_approval.py backend/tests/test_risk_engine_rejection.py backend/tests/test_risk_session_market_checks.py
git diff -- backend/strategies backend/risk backend/tests docs/sat3_strategy_risk_engine.md
git status --short
```

## 15. Hermes 보고 형식

```text
Phase 6 완료 보고

1. 생성/수정 파일:
2. Strategy Engine 구조:
3. SignalIntent 모델:
4. Risk Engine 체크 목록:
5. RiskDecision 모델:
6. 거절 코드:
7. Audit Event 연결:
8. 테스트 결과:
9. 금지 영역 변경 여부:
10. git diff 요약:
11. git status:
12. 커밋 여부: 미수행
```
