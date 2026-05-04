# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 05. Phase 4 - Market Regime Engine

## 1. Phase 목적

SAT3는 종목을 평가하기 전에 **시장 자체가 불장인지, 중립인지, 베어장인지** 먼저 평가해야 한다.

이 Phase의 목표는 시장 상태를 정량점수로 계산하는 Market Regime Engine을 만드는 것이다.

```text
핵심 원칙:
- 종목 평가보다 시장 평가가 먼저다.
- 시장이 Bull이면 종목 선정 점수에 가산점을 줄 수 있다.
- 시장이 Neutral이면 기본값을 유지한다.
- 시장이 Bear이면 종목 선정 점수에 감점을 주거나 신규매수를 차단한다.
- 시장 상태 판단도 KIS API 데이터 기반 정량평가로 수행한다.
```

## 2. 작업 범위

생성 권장 구조:

```text
backend/market/
├─ __init__.py
├─ market_regime.py
├─ index_trend.py
├─ market_breadth.py
├─ market_momentum.py
├─ market_volatility.py
├─ trading_value.py
├─ sector_strength.py
├─ investor_flow.py
└─ regime_config.py

backend/tests/test_market_regime_*.py
docs/sat3_market_regime_engine.md
```

## 3. 금지 사항

```text
금지:
- KIS 외부 시장 데이터 사용
- 임의 지수 데이터 생성
- API 실패 시 시장 상태 추정
- Bear 상태에서 신규매수 허용 기본값 설정
- 전략/주문 로직 수정
- 실제 주문 실행
```

## 4. Market Regime Score 구조

기본 점수 구조:

```text
Market Regime Score =
Index Trend Score
+ Market Breadth Score
+ Market Momentum Score
+ Volatility Stability Score
+ Trading Value Score
+ Sector Strength Score
+ Foreign/Institution Flow Score
- Market Risk Penalty
```

권장 배점:

```text
Index Trend Score              0~25
Market Breadth Score           0~20
Market Momentum Score          0~15
Volatility Stability Score     0~15
Trading Value Score            0~10
Sector Strength Score          0~10
Foreign/Institution Flow Score 0~5
Market Risk Penalty            0~40 감점
```

최종 0~100점으로 정규화한다.

분류 기준:

```text
Bull    : 70점 이상
Neutral : 40~69점
Bear    : 39점 이하
```

## 5. Market Regime 결과 객체

```python
@dataclass(frozen=True)
class MarketRegimeResult:
    regime: Literal["BULL", "NEUTRAL", "BEAR"]
    score: float

    index_trend_score: float
    market_breadth_score: float
    market_momentum_score: float
    volatility_stability_score: float
    trading_value_score: float
    sector_strength_score: float
    foreign_institution_flow_score: float
    market_risk_penalty: float

    candidate_score_adjustment: float
    allow_new_buy: bool
    min_candidate_score_required: float

    reasons: tuple[str, ...]
    source_endpoints: tuple[str, ...]
    evaluated_at: datetime
```

## 6. 시장 상태별 정책

```text
Bull:
- candidate_score_adjustment: +5 ~ +10
- allow_new_buy: true
- min_candidate_score_required: 기본값 또는 소폭 완화
- 단, 손실 제한/리스크 제한은 완화하지 않는다.

Neutral:
- candidate_score_adjustment: 0
- allow_new_buy: true
- min_candidate_score_required: 기본값

Bear:
- candidate_score_adjustment: -15 ~ -30
- allow_new_buy: false 또는 기준 강화
- min_candidate_score_required: 대폭 상향 또는 999
```

주의:

```text
불장이라고 리스크 엔진 기준을 완화하지 않는다.
불장 보정은 후보 점수와 기회 확장에만 적용한다.
베어장에서 allow_new_buy=false이면 종목 점수와 무관하게 신규매수 차단이다.
```

## 7. 평가 항목 상세

### 7.1 Index Trend Score

평가 대상:

```text
- KOSPI 추세
- KOSDAQ 추세
- 현재가와 5일/20일/60일선 관계
- 당일 지수 등락률
- 장중 추세 안정성
```

KIS API 출처 후보:

```text
- 국내업종 현재지수
- 국내업종 일자별지수
- 국내업종 시간별지수
```

배점 예시:

```text
KOSPI 추세: 0~8
KOSDAQ 추세: 0~10
양대 지수 동조성: 0~4
장중 추세 안정성: 0~3
```

### 7.2 Market Breadth Score

평가 대상:

```text
- 상승 종목 수 / 하락 종목 수
- 상승 종목 비율
- 상승 업종 비율
- 급등 종목 확산도
- 급락 종목 비율
```

출처 후보:

```text
- 등락률순위
- 업종 현재지수
- 상승/하락 상위 데이터
```

### 7.3 Market Momentum Score

평가 대상:

```text
- 지수 당일 모멘텀
- 지수 5일/20일 모멘텀
- 체결강도 상위 종목 확산
- 거래량 증가 종목 수
- 신고가 근접 종목 수
```

출처 후보:

```text
- 체결강도상위
- 거래량순위
- 신고/신저근접
- 업종 시간별지수
```

### 7.4 Volatility Stability Score

점수는 변동성이 안정적일수록 높다.

평가 대상:

```text
- 지수 장중 변동폭
- VI 발동/근접 종목 수
- 급등락 혼재 여부
- 장중 추세 일관성
```

출처 후보:

```text
- 변동성완화장치 현황
- 업종 시간별지수
- 상하한가 포착
```

### 7.5 Trading Value Score

평가 대상:

```text
- KOSPI/KOSDAQ 거래대금
- 전일 대비 거래대금 증가율
- 거래대금 상위 종목 확산
```

### 7.6 Sector Strength Score

평가 대상:

```text
- 상승 업종 수
- 주도 업종 강도
- 업종 추세 지속성
- 특정 업종 과열 여부
```

### 7.7 Foreign/Institution Flow Score

평가 대상:

```text
- 외국인 순매수
- 기관 순매수
- 코스닥 수급
- 주도 섹터 수급
```

비중은 낮게 둔다.

### 7.8 Market Risk Penalty

감점 대상:

```text
- KOSPI/KOSDAQ 동반 급락
- KOSDAQ 급락
- 하락 종목 비율 과다
- VI 발동 종목 급증
- 거래대금 급감
- 장중 저점 이탈
- 급등락 혼재 심화
- 장 마감 임박
```

정책:

```text
Market Risk Penalty >= 25:
- 후보 점수 추가 감점
- 신규매수 기준 강화

Market Risk Penalty >= 35:
- 신규매수 전체 차단
```

## 8. Audit Log 연결

Market Regime 평가 후 반드시 이벤트를 남긴다.

```text
event_type: MARKET_REGIME_EVALUATED
payload:
- regime
- score
- 세부 점수
- market_risk_penalty
- candidate_score_adjustment
- allow_new_buy
- min_candidate_score_required
- reasons
- source_endpoints
```

## 9. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_market_regime_score.py
backend/tests/test_market_regime_policy.py
backend/tests/test_market_regime_data_unavailable.py
```

필수 테스트:

```text
1. 70점 이상이면 BULL
2. 40~69점이면 NEUTRAL
3. 39점 이하이면 BEAR
4. BULL이면 candidate_score_adjustment가 양수
5. NEUTRAL이면 adjustment가 0
6. BEAR이면 adjustment가 음수 또는 allow_new_buy=false
7. Risk Penalty가 높으면 신규매수 차단
8. KIS 데이터 unavailable이면 평가 실패 또는 UNKNOWN 처리
9. API 실패 시 임의 시장 상태 추정 금지
10. MARKET_REGIME_EVALUATED audit event 생성
```

## 10. 문서 산출물

```text
docs/sat3_market_regime_engine.md
```

포함 내용:

```text
- Market Regime Engine 목적
- 점수 구조
- 항목별 평가 기준
- 시장 상태별 정책
- Candidate Score 보정 방식
- Risk Engine과 연결 방식
- Audit Log payload
- Dashboard 표시 요구사항
```

## 11. 검증 명령

```bash
pytest backend/tests/test_market_regime_score.py backend/tests/test_market_regime_policy.py backend/tests/test_market_regime_data_unavailable.py
git diff -- backend/market backend/tests docs/sat3_market_regime_engine.md
git status --short
```

## 12. Hermes 보고 형식

```text
Phase 4 완료 보고

1. 생성/수정 파일:
2. Market Regime 점수 구조:
3. Bull/Neutral/Bear 분류 기준:
4. 시장 보정값 정책:
5. Risk Penalty 정책:
6. KIS API 실패 시 처리:
7. Audit Event 연결:
8. 테스트 결과:
9. 금지 영역 변경 여부:
10. git diff 요약:
11. git status:
12. 커밋 여부: 미수행
```
