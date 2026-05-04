# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 06. Phase 5 - KOSPI/KOSDAQ Common Stock Scanner + Quant Candidate Evaluation

## 1. Phase 목적

이 Phase의 목표는 SAT3의 **정량 조건 기반 후보 발굴 Scanner**와 **후보 점수화 Quant Candidate Engine**의 기반을 구현하는 것이다.

SAT3 Scanner는 단순히 KIS API에서 종목을 긁어오는 수집기가 아니다.  
Scanner는 후보 발굴 단계부터 정량 조건을 적용해야 한다.

```text
핵심 원칙:
- Scanner는 정량 조건 기반 후보 발굴기다.
- Scanner는 후보 발굴과 1차 필터링까지만 수행한다.
- Scanner는 매수/매도 신호를 만들지 않는다.
- Scanner는 주문 수량, 손절가, 익절가를 계산하지 않는다.
- Quant Candidate Engine은 Scanner 후보를 더 깊게 점수화하고 우선순위화한다.
- Strategy Engine은 이 Phase에서 구현하지 않는다.
- Risk Engine은 이 Phase에서 구현하지 않는다.
- Order Engine은 이 Phase에서 구현하지 않는다.
- 모든 데이터는 KIS API Gateway를 통해 들어온 KIS_API source 데이터만 사용한다.
- 외부 크롤링, 수동 종목 리스트, 가짜 가격/거래량/체결 데이터는 금지한다.
```

역할 분리는 아래와 같이 고정한다.

```text
Scanner:
정량 기준을 만족한 후보를 발굴한다.

Quant Candidate Engine:
스캐너 후보를 점수화하고 후보 간 우선순위를 만든다.

Strategy Engine:
점수화된 후보 중 실제 진입/청산 신호를 만든다. Phase 5에서는 구현 금지.

Risk Engine:
실전 주문 가능 여부를 최종 검증한다. Phase 5에서는 구현 금지.
```

---

## 2. 매매 대상 Universe 정책

SAT3의 매매 대상은 **KOSPI/KOSDAQ 보통주**로 제한한다.

```text
매매 허용:
- KOSPI common stock
- KOSDAQ common stock
```

```text
매매 제외:
- ETF
- ETN
- ELW
- REIT
- SPAC
- preferred stock
- warrant
- inverse product
- leveraged product
- management issue
- investment warning/caution/risk issue
- trading halt issue
- delisting/administrative issue
- product_type UNKNOWN
- KOSPI/KOSDAQ 외 시장
```

중요 원칙:

```text
상품 유형을 알 수 없으면 제외한다.
KOSPI/KOSDAQ 여부를 확인할 수 없으면 제외한다.
ETF인지 아닌지 확실하지 않으면 제외한다.
KIS API source metadata 없이 종목명 패턴만으로 허용 판단하지 않는다.
```

종목명 패턴은 **보조적인 안전 제외 조건**으로만 사용할 수 있다. 최종 허용 판단은 KIS API source metadata 기반이어야 한다.

---

## 3. 작업 범위

생성 권장 구조:

```text
backend/scanner/
├─ __init__.py
├─ scanner_types.py
├─ scanner_config.py
├─ candidate.py
├─ exclusion_reasons.py
├─ common_filters.py
├─ scanner_engine.py
├─ rapid_surge_scanner.py
├─ liquidity_momentum_scanner.py
├─ breakout_scanner.py
├─ pullback_rebound_scanner.py
└─ scan_audit.py

backend/quant/
├─ __init__.py
├─ candidate_score.py
├─ score_components.py
├─ scoring_config.py
├─ rapid_surge_score.py
├─ pullback_score.py
├─ market_adjustment.py
├─ quant_evaluator.py
└─ quant_audit.py

backend/tests/test_scanner_*.py
backend/tests/test_quant_*.py
docs/sat3_scanner_quant_engine.md
```

과도한 구현을 피하기 위해 Phase 5에서는 실제 KIS HTTP 호출, 실제 백그라운드 스캔 루프, 실제 전략 신호, 실제 주문 흐름을 만들지 않는다.

---

## 4. 금지 사항

```text
금지:
- 매수/매도 주문 실행
- Strategy Signal 생성
- Risk Engine 승인 처리
- Order / Portfolio 구현
- 실제 KIS HTTP 호출 구현
- requests/httpx 추가
- KIS 외부 종목 리스트 사용
- 수동 CSV 종목 리스트 사용
- 임의 후보 생성
- API 실패 시 후보 유지
- fake price/fake volume/fake fill 사용
- Scanner에서 매수/매도 신호 생성
- Scanner에서 주문 수량 계산
- Scanner에서 손절/익절가 확정
- Scanner에서 Risk Engine 역할 수행
- ETF/ETN/ELW/REIT/SPAC/우선주/인버스/레버리지 상품 후보 통과
- 상품 유형 UNKNOWN 종목 후보 통과
- KOSPI/KOSDAQ 외 시장 후보 통과
- Telegram 추가 구현
- DB 연결 구현
- .env 수정
- secret/token/account/chat_id 원문 노출
```

---

## 5. Scanner Type

Phase 5는 급등주 단타만 단일 전략으로 고정하지 않는다.  
승률과 수익률 개선을 위해 **시장상태 기반 멀티 스캐너 구조**를 사용한다.

```text
Scanner Type:
1. RAPID_SURGE
2. LIQUIDITY_MOMENTUM
3. BREAKOUT
4. PULLBACK_REBOUND
```

### 5.1 RAPID_SURGE

급등 초기 후보를 포착한다.

정량 조건 후보:

```text
- intraday_change_rate >= configured_min_surge_rate
- intraday_change_rate <= configured_max_surge_rate
- volume_ratio_vs_recent_avg >= configured_min_volume_burst_ratio
- trading_value >= configured_min_trading_value
- execution_strength >= configured_min_execution_strength
- spread_rate <= configured_max_spread_rate
- pullback_from_high <= configured_max_pullback_from_high
- vi_status != ACTIVE
```

### 5.2 LIQUIDITY_MOMENTUM

거래대금 상위 + 안정적 상승 모멘텀 후보를 포착한다.  
급등주보다 체결 품질과 승률 보완 목적이 크다.

정량 조건 후보:

```text
- trading_value_rank <= configured_max_trading_value_rank
- trading_value >= configured_min_large_trading_value
- intraday_change_rate within configured_momentum_change_rate_range
- volume_ratio_vs_recent_avg >= configured_min_momentum_volume_ratio
- current_price > short_term_moving_average
- spread_rate <= configured_tight_spread_rate
```

### 5.3 BREAKOUT

당일 고점/전고점/신고가 근접 돌파 후보를 포착한다.

정량 조건 후보:

```text
- current_price >= intraday_high * configured_intraday_high_proximity
- current_price >= recent_high_20d * configured_recent_high_proximity
- volume_ratio_vs_recent_avg >= configured_min_breakout_volume_ratio
- trading_value >= configured_min_trading_value
- execution_strength >= configured_min_breakout_execution_strength
- market_regime in ["BULL", "NEUTRAL"]
```

### 5.4 PULLBACK_REBOUND

강한 종목의 눌림 후 재상승 후보를 포착한다.  
추격매수 위험을 줄이고 승률을 보완하는 역할이다.

정량 조건 후보:

```text
- prior_intraday_gain >= configured_min_prior_gain
- pullback_from_high within configured_pullback_depth_range
- rebound_volume_ratio >= configured_min_rebound_volume_ratio
- support_holding_score >= configured_min_support_holding_score
- spread_rate <= configured_max_spread_rate
- trading_value >= configured_min_trading_value
```

---

## 6. Scanner 공통 정량 필터

모든 scanner_type은 아래 공통 필터를 먼저 통과해야 한다.

```text
Common Scanner Filter:
- market in ["KOSPI", "KOSDAQ"]
- product_type == "COMMON_STOCK"
- current_price between configured_min_price and configured_max_price
- trading_value >= minimum_trading_value
- volume >= minimum_volume
- spread_rate <= maximum_spread_rate
- is_trading_halted == false
- is_management_issue == false
- is_investment_warning == false
- source == "KIS_API"
```

후보가 탈락하면 반드시 excluded_reason과 metrics를 남긴다.

---

## 7. 제외 사유 코드

제외 사유는 enum 또는 상수로 정의한다.

```text
NOT_KOSPI_KOSDAQ
NOT_COMMON_STOCK
ETF_EXCLUDED
ETN_EXCLUDED
ELW_EXCLUDED
REIT_EXCLUDED
SPAC_EXCLUDED
PREFERRED_STOCK_EXCLUDED
WARRANT_EXCLUDED
INVERSE_EXCLUDED
LEVERAGED_EXCLUDED
UNKNOWN_PRODUCT_TYPE
PRICE_TOO_HIGH
PRICE_TOO_LOW
TRADING_VALUE_TOO_LOW
VOLUME_TOO_LOW
SPREAD_TOO_WIDE
TRADING_HALTED
MANAGEMENT_ISSUE
INVESTMENT_WARNING
VI_ACTIVE
KIS_SOURCE_INVALID
DATA_UNAVAILABLE
SCANNER_CONDITION_NOT_MET
MARKET_REGIME_BLOCKED
```

---

## 8. Scanner 출력 모델

Scanner 출력은 단순 종목코드 리스트가 아니다.  
후보 편입/탈락의 정량 근거를 포함해야 한다.

```python
@dataclass(frozen=True)
class ScannerCandidate:
    symbol: str
    symbol_name: str | None
    market: Literal["KOSPI", "KOSDAQ"]
    product_type: Literal["COMMON_STOCK"]
    scanner_type: ScannerType
    discovered_at: datetime
    discovered_reason: tuple[str, ...]
    metrics: dict[str, float | int | str | bool]
    source_endpoints: tuple[str, ...]
    source: Literal["KIS_API"]
    scan_run_id: str
    included: bool
    excluded_reason: str | None
```

```python
@dataclass(frozen=True)
class ScanRunResult:
    scan_run_id: str
    scanner_type: ScannerType
    started_at: datetime
    completed_at: datetime
    market_regime: str
    collected_count: int
    excluded_count: int
    included_count: int
    candidates: tuple[ScannerCandidate, ...]
    source_endpoints: tuple[str, ...]
    data_quality_warnings: tuple[str, ...]
```

Scanner는 아래를 만들면 안 된다.

```text
- BuySignal
- SellSignal
- OrderIntent
- RiskDecision
- StopLoss / TakeProfit 확정값
```

---

## 9. Quant Candidate Engine 역할

Scanner가 정량 조건으로 발굴한 후보를 더 깊게 점수화한다.

```text
Scanner:
“이 종목을 후보로 볼 만한 최소 정량 조건을 통과했는가?”

Quant Candidate Engine:
“이 후보가 다른 후보보다 얼마나 좋은가?”
```

공통 점수:

```text
- liquidity_score
- spread_score
- volume_score
- momentum_score
- trend_score
- orderbook_score
- volatility_safety_score
- market_regime_adjustment
- symbol_risk_penalty
```

RAPID_SURGE 전용 점수:

```text
- surge_velocity_score
- volume_burst_score
- intraday_high_proximity_score
- vi_proximity_penalty
- pullback_failure_penalty
```

PULLBACK_REBOUND 전용 점수:

```text
- prior_strength_score
- pullback_depth_score
- rebound_confirmation_score
- support_holding_score
```

---

## 10. Quant 점수 구조

기본 점수 구조:

```text
Base Candidate Score =
Liquidity Score
+ Spread Score
+ Volume Score
+ Momentum Score
+ Trend Score
+ Orderbook Score
+ Volatility Safety Score
+ Scanner Specific Score
- Symbol Risk Penalty
```

시장 보정 후:

```text
Adjusted Candidate Score =
Base Candidate Score + MarketRegimeResult.candidate_score_adjustment
```

최종 판단:

```text
if MarketRegimeResult.allow_new_buy == false:
    decision = REJECT_MARKET_REGIME

elif adjusted_score >= MarketRegimeResult.min_candidate_score_required:
    decision = PASS

elif adjusted_score >= watch_threshold:
    decision = WATCH

else:
    decision = REJECT_SCORE
```

중요:

```text
PASS는 매수 신호가 아니다.
PASS는 Strategy Engine에 넘길 수 있는 후보라는 뜻이다.
```

---

## 11. Market Regime 연동

Phase 4의 MarketRegimeResult를 반드시 사용한다.

```text
BULL:
- 모든 scanner 활성 가능
- candidate_score_adjustment 적용
- RAPID_SURGE / BREAKOUT 적극 허용

NEUTRAL:
- LIQUIDITY_MOMENTUM / PULLBACK_REBOUND 중심
- RAPID_SURGE는 고득점 후보만 허용
- BREAKOUT은 제한적 허용

BEAR:
- 신규매수 차단 우선
- RAPID_SURGE / BREAKOUT 비활성 또는 강한 감점
- 후보 점수 감점

UNKNOWN:
- 신규매수 차단
- 후보는 평가 가능하더라도 주문 후보로 올리지 않음
```

---

## 12. Audit 연결

Scanner:

```text
SCAN_STARTED
SCAN_COMPLETED
CANDIDATE_DISCOVERED
CANDIDATE_EXCLUDED
```

Quant:

```text
QUANT_EVALUATED
```

각 이벤트는 다음 ID와 연결 가능해야 한다.

```text
- scan_run_id
- evaluation_id
- correlation_id
```

Audit payload에는 최소한 아래 항목이 포함되어야 한다.

```text
- scanner_type
- symbol
- included
- excluded_reason
- discovered_reason
- metrics
- source_endpoints
- market_regime
- base_score
- adjusted_score
- decision
- data_quality_warnings
```

---

## 13. 문서 산출물

```text
docs/sat3_scanner_quant_engine.md
```

포함 내용:

```text
- Scanner 역할과 금지 역할
- KOSPI/KOSDAQ 보통주 제한 정책
- ETF/ETN/ELW/REIT/SPAC/우선주/UNKNOWN 제외 정책
- Scanner Type별 정량 조건
- ScannerCandidate / ScanRunResult 모델
- Quant 점수 구조
- Market Regime 보정 방식
- 제외 사유 코드
- Audit Log 구조
- Dashboard 후보 보드 요구사항
```

---

## 14. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_scanner_candidate.py
backend/tests/test_scanner_common_filters.py
backend/tests/test_scanner_types.py
backend/tests/test_scanner_audit.py
backend/tests/test_quant_candidate_score.py
backend/tests/test_quant_market_adjustment.py
backend/tests/test_quant_data_unavailable.py
```

필수 테스트:

```text
1. ETF는 후보에 포함되지 않는다.
2. ETN/ELW/REIT/SPAC/우선주/인버스/레버리지/UNKNOWN product_type은 제외된다.
3. KOSPI/KOSDAQ 외 시장은 제외된다.
4. source != KIS_API이면 제외된다.
5. 공통 필터 통과/실패가 정량 조건에 따라 결정된다.
6. RAPID_SURGE 정량 조건 통과/실패 테스트.
7. LIQUIDITY_MOMENTUM 정량 조건 통과/실패 테스트.
8. BREAKOUT 정량 조건 통과/실패 테스트.
9. PULLBACK_REBOUND 정량 조건 통과/실패 테스트.
10. 후보 편입 사유가 기록된다.
11. 탈락 사유가 기록된다.
12. Scanner가 BuySignal/SellSignal/OrderIntent를 만들지 않는다.
13. Quant Candidate Score 계산 테스트.
14. Market Regime adjustment 반영 테스트.
15. BEAR/UNKNOWN에서 주문 후보로 올리지 않는 테스트.
16. QUANT_EVALUATED audit event 생성 테스트.
17. 기존 테스트가 깨지지 않는다.
```

---

## 15. 검증 명령

```bash
pytest backend/tests/test_scanner_candidate.py backend/tests/test_scanner_common_filters.py backend/tests/test_scanner_types.py backend/tests/test_scanner_audit.py backend/tests/test_quant_candidate_score.py backend/tests/test_quant_market_adjustment.py backend/tests/test_quant_data_unavailable.py
pytest

git diff -- backend/scanner backend/quant backend/tests docs/sat3_scanner_quant_engine.md
git status --short
```

---

## 16. Hermes 보고 형식

```text
Phase 5 완료 보고

1. 생성/수정 파일:
2. Scanner 역할 정의:
3. Scanner Type별 정량 조건:
4. KOSPI/KOSDAQ 보통주 제한 정책:
5. ETF/파생/우선주/UNKNOWN 제외 정책:
6. Candidate 모델:
7. Quant Score 구조:
8. Market Regime 보정 적용 방식:
9. Audit Event 연결:
10. 테스트 결과:
11. 기존 테스트 유지 여부:
12. 금지 영역 변경 여부:
13. git diff 요약:
14. git status:
15. 커밋 여부: 미수행
```
