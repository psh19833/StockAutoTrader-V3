# SAT3 Strategy + Risk Engine

> SAT3 Phase 6 구현 완료 기준 문서
> 마지막 수정: 2026-05-04

---

## 1. Strategy & Order 분리 원칙

SAT3에서 Strategy와 Order는 엄격하게 분리된다.

```
Quant PASS ──→ Strategy Signal ──→ Risk Decision ──→ LiveOrderGate ──→ Order
   (후보)       (의도)            (승인)            (최종 게이트)      (실행)
```

- **Quant PASS** = "이 종목은 정량적으로 좋다" (매수 신호 아님)
- **StrategySignal** = "이 종목을 사고 싶다" (주문 아님)
- **RiskDecision APPROVED** = "리스크 검증 통과" (주문 실행 아님)
- **LiveOrderGate 통과** = 비로소 실제 주문 제출 가능

---

## 2. Strategy Types (5종)

| Type | 목적 | Market Regime |
|------|------|--------------|
| RAPID_SURGE_SCALPING | 급등 초기 단타 | BULL 적극, NEUTRAL 고득점만 |
| LIQUIDITY_MOMENTUM_FOLLOW | 거래대금 상위 + 상승 추세 | BULL/NEUTRAL |
| BREAKOUT_FOLLOW | 고점 돌파 추격 | BULL/NEUTRAL |
| PULLBACK_REBOUND | 눌림 후 재상승 | BULL/NEUTRAL 중심 |
| FAST_EXIT | 빠른 청산 | 전 Regime |

### Scanner → Strategy 매핑

| Scanner | Strategy |
|---------|----------|
| RAPID_SURGE | RAPID_SURGE_SCALPING |
| LIQUIDITY_MOMENTUM | LIQUIDITY_MOMENTUM_FOLLOW |
| BREAKOUT | BREAKOUT_FOLLOW |
| PULLBACK_REBOUND | PULLBACK_REBOUND |

---

## 3. StrategySignal Model

```python
@dataclass(frozen=True)
class StrategySignal:
    signal_id: str              # 신호 고유 ID
    correlation_id: str         # 추적용 correlation ID
    symbol: str                 # 종목 코드
    side: str                   # BUY / SELL
    strategy_type: StrategyType # 전략 타입
    confidence: float           # 신뢰도 (0.0 ~ 1.0)
    source_quant_id: str        # 연결된 Quant 평가 ID
    scanner_type: str           # 연결된 Scanner Type
    market_regime: str          # 신호 생성 시점 시장 상태
    expected_entry_price: float # 예상 진입가
    suggested_stop_loss_rate: float
    suggested_take_profit_rate: float
    suggested_time_exit_minutes: int
    evidence: tuple[str, ...]   # 판단 근거
    created_at: datetime
    source_endpoints: tuple[str, ...]
    data_quality_warnings: tuple[str, ...]
```

### 신호 생성 조건

- Quant Decision이 **PASS**인 경우에만 BUY 신호 생성
- WATCH/REJECT → 신호 생성 금지
- Market Regime **allow_new_buy=false** → 신호 생성 금지
- Strategy Policy에서 비활성화된 전략 → 신호 생성 금지
- 신뢰도가 최소 기준 미달 → 신호 생성 금지

---

## 4. Strategy Policy (Market Regime별)

### BULL
- 모든 전략 활성 (RAPID_SURGE, LIQUIDITY_MOMENTUM, BREAKOUT, PULLBACK)
- RAPID_SURGE min_confidence: 0.60
- BREAKOUT min_confidence: 0.70

### NEUTRAL
- 모든 전략 활성이나 진입 기준 강화
- RAPID_SURGE min_confidence: 0.75 (고득점만)
- BREAKOUT min_confidence: 0.80 (제한적)

### BEAR
- **모든 전략 비활성** → 신규 BUY 신호 생성 금지

### UNKNOWN
- **모든 전략 비활성** → 신규 BUY 신호 생성 금지

---

## 5. Risk Engine

Risk Engine은 Strategy Signal을 받아 주문 허용 여부를 최종 검증한다.
**RiskDecision APPROVED도 실제 주문 실행이 아니다.**

### 검증 순서

1. **LIVE_TRADING_ENABLED** — false면 모든 주문 차단
2. **EMERGENCY_STOP** — 활성화 시 모든 주문 차단
3. **Session State** — REGULAR_MARKET만 신규매수 허용
4. **Market Regime** — allow_new_buy=false면 차단
5. **Duplicate Order** — 동일 종목 미체결 주문 있으면 차단
6. **Duplicate Position** — 동일 종목 보유 중이면 차단
7. **Daily Loss Limit** — 일일 손실 한도 초과 시 차단

### BUY vs SELL 차등 적용

- BUY: 모든 7단계 검증
- SELL: Session/Market Regime 검증 완화 (청산은 CLOSED_HOLIDAY, SESSION_STATE_UNKNOWN 외 허용)

---

## 6. RiskDecision Model

```python
@dataclass(frozen=True)
class RiskDecision:
    risk_decision_id: str
    signal_id: str
    correlation_id: str
    symbol: str
    side: str                    # BUY / SELL
    status: RiskDecisionStatus   # APPROVED / REJECTED / BLOCKED
    allowed: bool                # 주문 허용 여부
    reason_code: str             # 판단 사유 코드
    reason_text: str             # 판단 사유 설명
    checked_items: tuple         # 검증 완료된 항목
    failed_items: tuple          # 실패한 검증 항목
    market_regime: str
    session_state: str
    requested_amount: int
    created_at: datetime
```

---

## 7. Risk Reject Reasons (13종)

| 코드 | 검증 단계 |
|------|----------|
| LIVE_TRADING_DISABLED | 1단계 |
| EMERGENCY_STOP_BLOCKED | 2단계 |
| SESSION_BLOCKED | 3단계 |
| MARKET_REGIME_BLOCKED | 4단계 |
| DUPLICATE_ORDER_BLOCKED | 5단계 |
| SYMBOL_EXPOSURE_BLOCKED | 6단계 |
| DAILY_LOSS_LIMIT_BLOCKED | 7단계 |
| QUANT_REJECTED | (Quant REJECT) |
| REENTRY_BLOCKED | (재진입 제한) |
| POSITION_LIMIT_BLOCKED | (보유 한도) |
| STALE_DATA_BLOCKED | (데이터 만료) |
| DATA_QUALITY_BLOCKED | (데이터 품질) |
| UNKNOWN | (기타) |

---

## 8. Risk Limits (기본값)

```python
@dataclass(frozen=True)
class RiskLimits:
    max_position_count: int = 5           # 최대 보유 종목 수
    max_amount_per_symbol: int = 10_000_000  # 종목당 최대 투자금
    max_daily_loss_amount: int = 1_000_000   # 일일 최대 손실금
    max_daily_loss_rate: float = 0.03        # 일일 최대 손실률
    reentry_block_minutes: int = 30          # 재진입 제한 시간
    min_candidate_score_for_buy: float = 50.0 # 최소 후보 점수
```

---

## 9. Audit Events

| Event | Source | Trigger |
|-------|--------|---------|
| STRATEGY_SIGNAL_CREATED | strategy_audit.py | StrategySignal 생성 시 |
| RISK_APPROVED | risk_audit.py | RiskDecision allowed=true |
| RISK_REJECTED | risk_audit.py | RiskDecision allowed=false |

### Risk Audit Payload

```python
{
    "risk_decision_id": "...",
    "signal_id": "...",
    "symbol": "...",
    "side": "BUY",
    "allowed": false,
    "reason_code": "MARKET_REGIME_BLOCKED",
    "reason_text": "...",
    "checked_items": ["live_trading_enabled", ...],
    "failed_items": ["market_regime"],
    "market_regime": "BEAR",
    "session_state": "REGULAR_MARKET",
}
```

---

## 10. 청산 정책 (Fast Exit)

Phase 6에서 구조만 구현, 실제 청산 로직은 KIS 연동 후 적용.

### 청산 트리거 (구현 예정)

- 고정 손절: -1.0% ~ -2.0%
- 빠른 익절: +1.0% ~ +3.0%
- 시간 청산: 진입 후 15~30분 내 상승 실패
- 트레일링 스탑: 고점 대비 -0.5% ~ -1.2%
- 체결강도 약화 청산
- 장 마감 전 청산

### 중요 원칙

- 불장이라고 손절폭을 넓히지 않는다
- 급등주라는 이유로 Risk Engine을 우회하지 않는다
- 급등주라는 이유로 손절 기준을 완화하지 않는다

---

## 11. 구현 파일

```
backend/strategy/
├── __init__.py              # 패키지 익스포트
├── strategy_types.py        # StrategyType enum (5종)
├── signal.py                # StrategySignal dataclass
├── strategy_policy.py       # Market Regime별 정책
├── strategy_evaluator.py    # evaluate_entry(), evaluate_exit()
└── strategy_audit.py        # STRATEGY_SIGNAL_CREATED 변환

backend/risk/
├── __init__.py              # 패키지 익스포트
├── risk_types.py            # RiskDecisionStatus, RiskRejectReason
├── risk_decision.py         # RiskDecision dataclass
├── risk_config.py           # RiskLimits dataclass
├── risk_context.py          # RiskContext dataclass
├── risk_engine.py           # evaluate_risk() + 개별 check 함수
└── risk_audit.py            # RISK_APPROVED/REJECTED 변환
```

---

## 12. Phase 7~9 연동

- **Phase 7**: RiskDecision APPROVED → OrderIntent → LiveOrderGate → 실제 주문
- **Phase 8**: Strategy/Risk 성과 → EOD Report 전략별 성과 집계
- **Phase 9**: Preflight에서 Risk Engine, Strategy Engine 상태 확인
