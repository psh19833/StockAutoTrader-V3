# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 06B. Phase 5B - KOSPI/KOSDAQ Multi-Scanner + Rapid Surge Strategy Policy

## 1. Phase 목적

이 Phase의 목표는 Phase 5에서 구현된 Scanner/Quant 구조 위에, SAT3의 매매 Universe와 전략 방향을 명확히 고정하는 것이다.

SAT3는 **급등주 단타를 우선 전략으로 삼되, 급등주 하나만 쫓는 단일 전략 봇으로 만들지 않는다.**  
승률과 수익률을 동시에 개선하기 위해 시장상태 기반 멀티 스캐너 구조를 사용한다.

```text
정책 방향:
- KOSPI/KOSDAQ 보통주만 매매한다.
- ETF/ETN/ELW/REIT/SPAC/우선주/인버스/레버리지/UNKNOWN 상품은 제외한다.
- Scanner는 후보 발굴부터 정량 조건을 적용한다.
- RAPID_SURGE는 핵심 전략이지만 유일한 전략은 아니다.
- LIQUIDITY_MOMENTUM, BREAKOUT, PULLBACK_REBOUND로 승률을 보완한다.
- Market Regime에 따라 활성 스캐너와 전략 강도를 조절한다.
```

---

## 2. 최상위 Universe 정책

```text
SAT3 Scanner Universe = KOSPI/KOSDAQ common stock only
```

허용:

```text
- KOSPI common stock
- KOSDAQ common stock
- KIS API source metadata로 보통주임이 확인된 종목
```

제외:

```text
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
상품 유형을 알 수 없으면 통과시키지 않는다.
KOSPI/KOSDAQ 여부를 확인할 수 없으면 통과시키지 않는다.
KIS API source 없이 종목명만으로 안전하다고 판단하지 않는다.
```

---

## 3. Scanner의 정량 발굴 역할

Scanner는 단순 수집기가 아니다.

```text
Scanner 역할:
- KIS API Gateway를 통해 후보 데이터를 수집한다.
- KOSPI/KOSDAQ 보통주만 유지한다.
- 제외 상품을 정량/메타데이터 기준으로 제거한다.
- scanner_type별 정량 조건을 적용한다.
- 조건을 통과한 종목만 ScannerCandidate로 만든다.
- 후보 편입 사유와 탈락 사유를 모두 기록한다.
- 모든 metric과 source_endpoint를 남긴다.
```

Scanner가 하면 안 되는 일:

```text
- 매수 신호 생성
- 매도 신호 생성
- 주문 수량 계산
- 손절/익절가 확정
- Risk Engine 역할 수행
- 주문 허용 여부 판단
```

---

## 4. Multi-Scanner 정책

### 4.1 RAPID_SURGE

급등 초기 후보를 빠르게 포착한다.

```text
중점 지표:
- 당일 등락률
- 거래량 폭증
- 거래대금 증가
- 체결강도
- 호가 스프레드
- 당일 고점 근접도
- VI 위험
- 고점 대비 눌림폭
```

### 4.2 LIQUIDITY_MOMENTUM

거래대금이 충분하고 상승 모멘텀이 유지되는 종목을 포착한다.

```text
목적:
- 급등주보다 체결 품질이 안정적인 후보 확보
- 승률 보완
- 시장이 NEUTRAL일 때 과도한 추격매수를 줄임
```

### 4.3 BREAKOUT

당일 고점, 전고점, 신고가 근접 돌파 후보를 포착한다.

```text
목적:
- BULL 또는 강한 NEUTRAL에서 상승 추세를 적극 활용
- BEAR/UNKNOWN에서는 비활성 또는 강한 감점
```

### 4.4 PULLBACK_REBOUND

강한 종목의 눌림 후 재상승 후보를 포착한다.

```text
목적:
- 급등주 꼭대기 추격 위험 완화
- 지지 확인 후 진입으로 승률 보완
```

---

## 5. Scanner Type별 정량 조건

### RAPID_SURGE

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

### LIQUIDITY_MOMENTUM

```text
- trading_value_rank <= configured_max_trading_value_rank
- trading_value >= configured_min_large_trading_value
- intraday_change_rate within configured_momentum_change_rate_range
- volume_ratio_vs_recent_avg >= configured_min_momentum_volume_ratio
- current_price > short_term_moving_average
- spread_rate <= configured_tight_spread_rate
```

### BREAKOUT

```text
- current_price >= intraday_high * configured_intraday_high_proximity
- current_price >= recent_high_20d * configured_recent_high_proximity
- volume_ratio_vs_recent_avg >= configured_min_breakout_volume_ratio
- trading_value >= configured_min_trading_value
- execution_strength >= configured_min_breakout_execution_strength
- market_regime in ["BULL", "NEUTRAL"]
```

### PULLBACK_REBOUND

```text
- prior_intraday_gain >= configured_min_prior_gain
- pullback_from_high within configured_pullback_depth_range
- rebound_volume_ratio >= configured_min_rebound_volume_ratio
- support_holding_score >= configured_min_support_holding_score
- spread_rate <= configured_max_spread_rate
- trading_value >= configured_min_trading_value
```

---

## 6. Market Regime별 활성 정책

```text
BULL:
- 모든 scanner 활성 가능
- RAPID_SURGE / BREAKOUT 적극 허용
- LIQUIDITY_MOMENTUM / PULLBACK_REBOUND도 유지
- candidate_score_adjustment 적용

NEUTRAL:
- LIQUIDITY_MOMENTUM / PULLBACK_REBOUND 중심
- RAPID_SURGE는 고득점 후보만 허용
- BREAKOUT은 제한적 허용

BEAR:
- 신규매수 차단 우선
- RAPID_SURGE / BREAKOUT 비활성 또는 강한 감점
- 후보는 관찰 가능하더라도 주문 후보로 올리지 않음

UNKNOWN:
- 신규매수 차단
- 후보는 평가 가능하더라도 주문 후보로 올리지 않음
```

---

## 7. Quant Score 방향

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

RAPID_SURGE 전용:

```text
- surge_velocity_score
- volume_burst_score
- intraday_high_proximity_score
- vi_proximity_penalty
- pullback_failure_penalty
```

PULLBACK_REBOUND 전용:

```text
- prior_strength_score
- pullback_depth_score
- rebound_confirmation_score
- support_holding_score
```

중요:

```text
Quant PASS는 매수 신호가 아니다.
Quant PASS는 Strategy Engine으로 넘길 수 있는 후보라는 뜻이다.
```

---

## 8. 빠른 청산 정책 방향

급등주 전략은 매수보다 청산이 중요하다. 실제 구현은 Phase 6에서 한다.

필수 청산 정책:

```text
- 고정 손절
- 빠른 익절
- 부분 익절
- 트레일링 스탑
- 시간 손절
- 급락 감지 청산
- 체결강도 약화 청산
- 호가 매도벽/스프레드 악화 청산
- 장 마감 전 청산 정책
```

예시 정책값은 문서에만 둔다. 실제 기본값은 Phase 6에서 보수적으로 설정한다.

```text
예시:
- 손절: -1.0% ~ -2.0%
- 1차 익절: +1.0% ~ +2.0%
- 트레일링: 고점 대비 -0.5% ~ -1.2%
- 시간 손절: 진입 후 10~30분 내 상승 실패 시 정리
```

주의:

```text
불장이라고 손절폭을 넓히지 않는다.
급등주라는 이유로 Risk Engine을 우회하지 않는다.
급등주라는 이유로 손절 기준을 완화하지 않는다.
```

---

## 9. Risk Engine 추가 요구사항 후보

실제 구현은 Phase 6에서 한다.

```text
- 급등 후 과열 진입 차단
- VI 발동/근접 종목 차단 또는 강한 감점
- 호가 스프레드 과도 종목 차단
- 거래대금 부족 종목 차단
- 당일 급등 후 거래량 감소 종목 차단
- 동일 종목 재진입 제한
- 연속 손절 후 신규매수 제한
- 장 시작 직후 과도한 변동성 구간 제한
- 장 마감 임박 신규매수 차단
```

거절 코드 추가 후보:

```text
SURGE_OVERHEATED_BLOCKED
VI_RISK_BLOCKED
SPREAD_TOO_WIDE
TRADING_VALUE_TOO_LOW
VOLUME_FADE_BLOCKED
FAST_REENTRY_BLOCKED
LATE_SURGE_ENTRY_BLOCKED
```

---

## 10. Audit / Telegram 요구사항

Audit event 연결:

```text
SCAN_STARTED
SCAN_COMPLETED
CANDIDATE_DISCOVERED
CANDIDATE_EXCLUDED
QUANT_EVALUATED
```

Telegram 알림 대상 후보:

```text
- 고득점 급등주 후보 발견
- 스캔 요약
- 리스크 승인/거절
- 주문 제출
- 체결 확인
- 빠른 손절/익절 발생
- VI/과열 위험으로 차단
```

단, Phase 5B에서는 Telegram 추가 구현을 하지 않는다. Phase 3B의 정책을 사용한다.

---

## 11. 테스트 요구사항

```text
- ETF 상품 유형이면 Scanner 후보에서 제외된다.
- ETN/ELW/REIT/SPAC/우선주/인버스/레버리지/UNKNOWN 상품은 제외된다.
- KOSPI/KOSDAQ 외 시장은 제외된다.
- 개별 보통주는 KIS source metadata가 있을 때만 후보로 유지된다.
- Scanner는 정량 조건을 통과한 후보만 포함한다.
- RAPID_SURGE 정량 조건 통과/실패 테스트.
- LIQUIDITY_MOMENTUM 정량 조건 통과/실패 테스트.
- BREAKOUT 정량 조건 통과/실패 테스트.
- PULLBACK_REBOUND 정량 조건 통과/실패 테스트.
- Bear/UNKNOWN 시장에서는 주문 후보로 올리지 않는다.
- Scanner는 BuySignal/SellSignal/OrderIntent를 만들지 않는다.
- 민감정보는 어떤 로그/알림에도 노출되지 않는다.
```

---

## 12. 금지 사항

```text
금지:
- ETF를 후보로 허용
- ETF/ETN/ELW를 개별 주식과 같은 점수체계로 최종 허용
- KIS API source 없이 종목명만으로 안전하다고 판단
- 상품 유형 UNKNOWN 종목 통과
- Scanner가 매수 신호 생성
- Scanner가 주문 수량 계산
- Scanner가 손절/익절가 확정
- 급등주라는 이유로 Risk Engine 우회
- 급등주라는 이유로 손절 기준 완화
- 급등주 신호를 주문으로 직접 연결
- Telegram 후보 알림 폭주
- 임의 가격/거래량/체결 생성
```

---

## 13. Hermes 작업 지시

```text
Phase 5B 작업을 시작한다.

목표:
SAT3 Scanner와 Strategy 정책에 KOSPI/KOSDAQ 보통주 제한, ETF/파생상품 제외, 시장상태 기반 멀티 스캐너, 급등주 우선 단타 방향을 반영한다.

작업 범위:
1. docs/sat3_scanner_quant_engine.md에 Universe/Scanner/Quant 정책을 반영한다.
2. docs/sat3_strategy_risk_engine.md에 급등주 우선 + 멀티 전략 방향을 반영한다.
3. Scanner exclusion reason code 설계를 추가한다.
4. RAPID_SURGE / LIQUIDITY_MOMENTUM / BREAKOUT / PULLBACK_REBOUND 스캐너 정책을 문서화한다.
5. RapidSurge / LiquidityMomentum / MomentumBreakout / PullbackRebound / FastExit 전략 설계 초안을 추가한다.
6. Risk Engine 급등주 전용 거절 코드 후보를 문서화한다.
7. 테스트 계획을 문서화한다.

허용되는 코드 변경:
- Phase 5/6이 이미 구현된 상태라면 exclusion reason enum 또는 설정 스켈레톤 정도만 허용한다.
- 실제 주문 관련 코드는 수정하지 않는다.

금지:
- KIS 주문 API 호출부 수정 금지
- 실제 주문 실행 금지
- 전략을 주문과 직접 연결 금지
- 기존 SAT2 코드 무단 복사 금지
- ETF를 후보로 통과시키는 fallback 금지
- Scanner에서 매수/매도 신호 생성 금지

검증:
- git diff로 변경 파일을 확인한다.
- 테스트를 실행 가능한 범위에서 수행한다.
- 커밋은 하지 않는다.

보고 형식:
1. 작업 Phase
2. 변경 파일 목록
3. KOSPI/KOSDAQ 보통주 제한 반영 내용
4. ETF/파생/우선주/UNKNOWN 제외 정책 반영 내용
5. Scanner 정량 조건 반영 내용
6. 급등주 우선 + 멀티 스캐너 전략 반영 내용
7. 추가/수정한 거절 코드
8. 테스트 결과
9. 남은 리스크
10. git diff 요약
11. git status
```
