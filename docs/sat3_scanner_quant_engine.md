# SAT3 Scanner + Quant Engine

> SAT3 Phase 5 구현 완료 기준 문서
> 마지막 수정: 2026-05-04 (Phase 5B Checkpoint)

---

## 1. KOSPI/KOSDAQ 보통주 Universe 정책

SAT3의 매매 대상은 **KOSPI/KOSDAQ 보통주로만** 제한한다.

### 허용

- KOSPI common stock
- KOSDAQ common stock
- KIS API source metadata로 보통주임이 확인된 종목

### 제외

- ETF, ETN, ELW, REIT, SPAC
- 우선주(preferred stock), 워런트(warrant)
- 인버스(inverse), 레버리지(leveraged)
- 관리종목(management issue)
- 투자경고/주의/위험 종목(investment warning)
- 거래정지 종목(trading halt)
- 상장폐지/행정 이슈(delisting/administrative issue)
- product_type UNKNOWN
- KOSPI/KOSDAQ 외 시장

### 중요 원칙

- 상품 유형을 알 수 없으면 제외 (추정 금지)
- KOSPI/KOSDAQ 여부를 확인할 수 없으면 제외
- KIS API source metadata 없이 종목명만으로 허용 판단하지 않음
- 종목명 패턴은 보조적 안전 제외 조건으로만 사용

**구현 위치**: `backend/scanner/universe.py` — `check_universe()`

---

## 2. 제외 사유 코드

Scanner의 모든 제외에는 `ExclusionReason` enum을 통해 사유가 기록된다.

| 그룹 | 사유 코드 |
|------|----------|
| Universe/상품유형 | NOT_KOSPI_KOSDAQ, NOT_COMMON_STOCK, ETF_EXCLUDED, ETN_EXCLUDED, ELW_EXCLUDED, REIT_EXCLUDED, SPAC_EXCLUDED, PREFERRED_STOCK_EXCLUDED, WARRANT_EXCLUDED, INVERSE_EXCLUDED, LEVERAGED_EXCLUDED, UNKNOWN_PRODUCT_TYPE |
| 공통 정량 필터 | PRICE_TOO_HIGH, PRICE_TOO_LOW, TRADING_VALUE_TOO_LOW, VOLUME_TOO_LOW, SPREAD_TOO_WIDE, TRADING_HALTED, MANAGEMENT_ISSUE, INVESTMENT_WARNING, VI_ACTIVE, KIS_SOURCE_INVALID, DATA_UNAVAILABLE |
| Scanner 특화 | SCANNER_CONDITION_NOT_MET, MARKET_REGIME_BLOCKED |

Scanner-specific filter 실패 시에는 FilterResult의 구체적인 reason이 `ScannerCandidate.excluded_reason`으로 전파된다 (예: "VI_ACTIVE", "surge_rate 0.5 < min 2.0").

**구현 위치**: `backend/scanner/scanner_types.py`

---

## 3. Scanner 역할

Scanner는 **정량 조건 기반 후보 발굴기**다. 단순한 API 데이터 수집기가 아니다.

### Scanner 파이프라인

```
stock_data → Universe Check → Common Filter → Scanner Filter → ScannerCandidate
```

1. **Universe Check**: KOSPI/KOSDAQ 보통주 + KIS_API source 검증
2. **Common Filter**: 가격, 거래대금, 거래량, 스프레드, 거래정지, 관리종목, 투자경고
3. **Scanner Filter**: Scanner Type별 정량 조건

각 단계에서 탈락 시 `excluded_reason`이 기록된 `ScannerCandidate(included=False)`가 생성된다.

### Scanner가 하지 않는 일

- 매수/매도 신호 생성 (BuySignal/SellSignal 금지)
- 주문 수량 계산
- 손절가/익절가 확정
- Risk Engine 역할 수행
- 주문 허용 여부 판단

**구현 위치**: `backend/scanner/scanner_engine.py` — `run_scanner()`, `run_all_scanners()`

---

## 4. Scanner Type 4종

### 4.1 RAPID_SURGE — 급등 초기

급등 초기 후보를 빠르게 포착.

| 조건 | 기본값 |
|------|--------|
| intraday_change_rate | 2.0% ~ 30.0% |
| volume_ratio_vs_recent_avg | ≥ 1.5 |
| trading_value | ≥ 5억원 |
| execution_strength | ≥ 100 |
| spread_rate | ≤ 1.0% |
| pullback_from_high | ≤ 3.0% |
| vi_status | ≠ ACTIVE |

### 4.2 LIQUIDITY_MOMENTUM — 안정적 모멘텀

거래대금 상위 + 상승 추세.

| 조건 | 기본값 |
|------|--------|
| trading_value_rank | ≤ 100 |
| trading_value | ≥ 200억원 |
| intraday_change_rate | 0.5% ~ 5.0% |
| volume_ratio_vs_recent_avg | ≥ 1.2 |
| current_price > short_term_moving_average | 필수 |
| spread_rate | ≤ 0.3% |

### 4.3 BREAKOUT — 고점 돌파

당일 고점/20일 고점 근접 돌파.

| 조건 | 기본값 |
|------|--------|
| current_price ≥ intraday_high × 0.95 | 필수 |
| current_price ≥ recent_high_20d × 0.95 | 필수 |
| volume_ratio_vs_recent_avg | ≥ 1.5 |
| trading_value | ≥ 5억원 |
| execution_strength | ≥ 120 |
| market_regime | BULL / NEUTRAL |

### 4.4 PULLBACK_REBOUND — 눌림 후 재상승

강한 종목의 눌림 후 반등.

| 조건 | 기본값 |
|------|--------|
| prior_intraday_gain | ≥ 3.0% |
| pullback_from_high | 1.0% ~ 5.0% |
| rebound_volume_ratio | ≥ 1.0 |
| support_holding_score | ≥ 5.0 |
| spread_rate | ≤ 1.0% |
| trading_value | ≥ 5억원 |

**구현 위치**: `backend/scanner/filters.py`

---

## 5. Quant Engine 역할

Scanner가 정량 조건으로 발굴한 후보를 더 깊게 점수화하고 우선순위를 만든다.

### Scanner vs Quant

```
Scanner: "이 종목을 후보로 볼 만한 최소 정량 조건을 통과했는가?"
Quant:   "이 후보가 다른 후보보다 얼마나 좋은가?"
```

### 공통 점수 (7종, 각 0~10)

liquidity_score, spread_score, volume_score, momentum_score, trend_score, orderbook_score, volatility_safety_score

### RAPID_SURGE 전용 (5종)

surge_velocity_score, volume_burst_score, intraday_high_proximity_score, vi_proximity_penalty, pullback_failure_penalty

### PULLBACK_REBOUND 전용 (4종)

prior_strength_score, pullback_depth_score, rebound_confirmation_score, support_holding_score

### 최종 점수 공식

```
base_score = sum(7 common scores)
scanner_bonus = sum(scanner-specific scores) - sum(scanner penalties)
final_score = base_score + scanner_bonus - symbol_risk_penalty + market_regime_adjustment
```

### Decision

```
if not allow_new_buy → REJECT (MarketRegimeBlocked)
elif final_score >= pass_threshold → PASS
elif final_score >= watch_threshold → WATCH
else → REJECT
```

### 중요: PASS는 매수 신호가 아니다

Quant PASS는 Strategy Engine에 넘길 수 있는 후보라는 의미일 뿐이다. 실제 매수 판단은 Phase 6 Strategy + Risk Engine에서 수행한다.

**구현 위치**: `backend/quant/scoring_calculator.py` — `evaluate_candidate()`, `evaluate_candidates()`, `evaluate_scan_result()`

---

## 6. Market Regime 연동

Phase 4의 `MarketRegimeResult`를 통해 시장 상태가 반영된다.

| Regime | 정책 |
|--------|------|
| BULL | 모든 Scanner 활성, RAPID_SURGE/BREAKOUT 적극 허용, threshold 완화 |
| NEUTRAL | LIQUIDITY_MOMENTUM/PULLBACK_REBOUND 중심, RAPID_SURGE 고득점만 |
| BEAR | 신규매수 차단, RAPID_SURGE/BREAKOUT 비활성 |
| UNKNOWN | 신규매수 차단, 후보 평가는 가능하나 주문 후보로 올리지 않음 |

BEAR/UNKNOWN에서는 `allow_new_buy=False` → 모든 Quant 평가가 REJECT로 결정된다.

**구현 위치**: `scoring_calculator.py` — `determine_decision()` / `scoring_config.py` — regime_policies

---

## 7. Audit Event 연결

| Event | Trigger | Source |
|-------|---------|--------|
| SCAN_STARTED | Scanner 실행 시작 | `scanner/scanner_audit.py` |
| SCAN_COMPLETED | Scanner 실행 완료 | `scanner/scanner_audit.py` |
| CANDIDATE_DISCOVERED | 후보 편입 | `scanner/scanner_audit.py` |
| CANDIDATE_EXCLUDED | 후보 제외 | `scanner/scanner_audit.py` |
| QUANT_EVALUATED | Quant 평가 완료 | `quant/quant_audit.py` |

Audit payload에는 symbol, scanner_type, included, excluded_reason, metrics, source_endpoints, decision, scores 등이 포함된다.

Telegram 알림은 Phase 3B에서 구현된 인프라를 통해 SCAN_COMPLETED, CANDIDATE_DISCOVERED가 전송된다. QUANT_EVALUATED, CANDIDATE_EXCLUDED의 Telegram 포매터는 Phase 6 이후 추가 예정이다.

---

## 8. Phase 6 Strategy/Risk Engine으로 넘겨야 할 정보

Phase 6에서는 다음 정보가 Strategy Engine과 Risk Engine으로 전달된다:

### Scanner → Strategy Engine

- `ScanRunResult.candidates` (included=True 후보들)
- 각 `ScannerCandidate.metrics` (정량 데이터)
- `ScannerCandidate.excluded_reason` (제외 사유)

### Quant → Strategy Engine

- `QuantCandidateScore.final_score` (최종 점수)
- `QuantCandidateScore.decision` (PASS/WATCH/REJECT)
- `QuantCandidateScore.reasons` (판단 근거)

### Strategy/Risk Engine에서 추가할 것 (Phase 6)

- Strategy Signal (매수/매도 신호)
- Risk Gate (VI 과열, 거래대금 부족, 재진입 제한 등)
- 청산 정책 (손절, 익절, 트레일링 스탑, 시간 손절 등)
- 주문 허용 여부 최종 판단
