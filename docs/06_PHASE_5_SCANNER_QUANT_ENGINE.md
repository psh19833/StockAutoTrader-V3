# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 06. Phase 5 - Scanner + Quant Candidate Evaluation

## 1. Phase 목적

이 Phase의 목표는 SAT3의 종목 선정 체계를 만드는 것이다.

```text
핵심 원칙:
- Scanner는 후보 발굴만 한다.
- Quant Evaluation은 후보 점수를 계산한다.
- Strategy는 이 Phase에서 구현하지 않는다.
- Scanner와 Quant는 KIS API 데이터만 사용한다.
- 후보 편입/제외 사유를 모두 로그로 남긴다.
```

## 2. 작업 범위

생성 권장 구조:

```text
backend/scanner/
├─ __init__.py
├─ scanner_engine.py
├─ ranking_collectors.py
├─ candidate.py
├─ exclusion_filters.py
└─ scan_log_adapter.py

backend/quant/
├─ __init__.py
├─ candidate_score.py
├─ liquidity.py
├─ momentum.py
├─ volume.py
├─ orderbook.py
├─ trend.py
├─ fundamental.py
├─ risk_penalty.py
├─ scoring_config.py
└─ explanation.py

backend/tests/test_scanner_*.py
backend/tests/test_quant_*.py
docs/sat3_scanner_quant_engine.md
```

## 3. 금지 사항

```text
금지:
- 매수/매도 주문 실행
- Strategy Signal 생성
- Risk Engine 승인 처리
- KIS 외부 종목 리스트 사용
- 수동 CSV 종목 리스트 사용
- 임의 후보 생성
- API 실패 시 후보 유지
- fake price/fake volume 사용
```

## 4. Scanner 역할

Scanner는 후보만 수집한다.

입력 출처 후보:

```text
- 거래량순위
- 등락률순위
- 체결강도상위
- 호가잔량순위
- 신고/신저근접
- 상하한가 포착
- 종목조건검색
```

출력 모델:

```python
@dataclass(frozen=True)
class ScanCandidate:
    symbol: str
    symbol_name: str | None
    discovered_by: tuple[str, ...]
    source_endpoints: tuple[str, ...]
    raw_ranks: dict[str, int | float]
    scan_run_id: str
    discovered_at: datetime
```

Scanner가 하면 안 되는 일:

```text
- 매수 판단
- 주문 판단
- 포지션 판단
- 손절/익절 판단
- 가짜 후보 추가
```

## 5. Scanner 실행 결과

```python
@dataclass(frozen=True)
class ScanRunResult:
    scan_run_id: str
    started_at: datetime
    finished_at: datetime
    source_endpoints: tuple[str, ...]
    collected_count: int
    deduped_count: int
    excluded_count: int
    final_candidate_count: int
    candidates: tuple[ScanCandidate, ...]
    exclusions: tuple[CandidateExclusion, ...]
```

제외 결과:

```python
@dataclass(frozen=True)
class CandidateExclusion:
    symbol: str
    reason_code: str
    reason_text: str
    source_endpoints: tuple[str, ...]
```

## 6. Quant Evaluation 역할

후보 종목을 정량 점수화한다.

기본 점수 구조:

```text
Base Candidate Score =
Liquidity Score
+ Momentum Score
+ Volume Score
+ Orderbook Score
+ Trend Score
+ Fundamental Score
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

## 7. Quant 결과 모델

```python
@dataclass(frozen=True)
class QuantScoreResult:
    evaluation_id: str
    scan_run_id: str
    symbol: str
    symbol_name: str | None

    base_candidate_score: float
    adjusted_candidate_score: float
    market_regime_score: float
    market_adjustment: float

    liquidity_score: float
    momentum_score: float
    volume_score: float
    orderbook_score: float
    trend_score: float
    fundamental_score: float
    symbol_risk_penalty: float

    decision: Literal[
        "PASS",
        "WATCH",
        "REJECT_SCORE",
        "REJECT_MARKET_REGIME",
        "REJECT_DATA_UNAVAILABLE",
        "REJECT_RISK"
    ]

    reasons: tuple[str, ...]
    source_endpoints: tuple[str, ...]
    evaluated_at: datetime
    data_quality_warnings: tuple[str, ...]
```

## 8. 세부 점수 항목

### 8.1 Liquidity Score

출처:

```text
- 현재가
- 호가/예상체결
- 거래량순위
- 기간별시세
```

평가:

```text
- 거래대금
- 호가 스프레드
- 매수/매도 잔량 안정성
- 체결 가능성
```

### 8.2 Momentum Score

출처:

```text
- 등락률순위
- 현재가
- 당일분봉
- 일별분봉
- 신고/신저근접
```

평가:

```text
- 당일 등락률
- 분봉 상승 지속성
- 신고가 근접/돌파
- 급등 후 하락 전환 여부
```

### 8.3 Volume Score

출처:

```text
- 거래량순위
- 체결
- 시간대별체결
- 기간별시세
```

평가:

```text
- 현재 거래량 / 최근 평균 거래량
- 체결량 증가 지속성
- 순간 급증 후 소멸 여부
```

### 8.4 Orderbook Score

출처:

```text
- 호가/예상체결
- 실시간호가
- 호가잔량순위
```

평가:

```text
- 스프레드
- 매수잔량/매도잔량
- 매도벽
- 예상체결 흐름
```

### 8.5 Trend Score

출처:

```text
- 기간별시세
- 당일분봉
- 일별분봉
```

평가:

```text
- 단기/중기 이동평균 관계
- 고점/저점 구조
- 변동성 안정성
```

### 8.6 Fundamental Score

출처:

```text
- 주식기본조회
- 재무비율
- 수익성비율
- 안정성비율
- 성장성비율
```

단타 시스템에서는 진입 트리거보다 위험 필터 성격으로 낮은 비중을 둔다.

### 8.7 Symbol Risk Penalty

출처:

```text
- VI 현황
- 공매도
- 신용잔고
- 상하한가 포착
- 공시/시황 제목
```

감점:

```text
- VI 발동/근접
- 급등 후 거래량 감소
- 신용잔고 과다
- 공매도 급증
- 가격 상한 초과
- 데이터 stale
```

## 9. Audit Log 연결

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

각 이벤트는 `scan_run_id`, `evaluation_id`, `correlation_id`를 포함해야 한다.

## 10. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_scanner_engine.py
backend/tests/test_candidate_exclusion.py
backend/tests/test_quant_candidate_score.py
backend/tests/test_quant_market_adjustment.py
backend/tests/test_quant_data_unavailable.py
```

필수 테스트:

```text
1. Scanner가 후보를 수집하고 중복 제거
2. 제외 조건에 걸린 후보가 CandidateExclusion으로 기록
3. Scanner가 매수/주문 판단을 하지 않음
4. Base Candidate Score 계산
5. Bull market adjustment 적용
6. Neutral market adjustment 0 적용
7. Bear market adjustment 또는 신규매수 차단 적용
8. KIS 데이터 unavailable이면 평가 거절
9. source_endpoints 없는 데이터는 거절
10. QUANT_EVALUATED audit event 생성
```

## 11. 문서 산출물

```text
docs/sat3_scanner_quant_engine.md
```

포함 내용:

```text
- Scanner 역할과 금지 역할
- KIS API 기반 후보 수집 방식
- Quant 점수 구조
- Market Regime 보정 방식
- 제외 사유 코드
- Audit Log 구조
- Dashboard 후보 보드 요구사항
```

## 12. 검증 명령

```bash
pytest backend/tests/test_scanner_engine.py backend/tests/test_candidate_exclusion.py backend/tests/test_quant_candidate_score.py backend/tests/test_quant_market_adjustment.py backend/tests/test_quant_data_unavailable.py
git diff -- backend/scanner backend/quant backend/tests docs/sat3_scanner_quant_engine.md
git status --short
```

## 13. Hermes 보고 형식

```text
Phase 5 완료 보고

1. 생성/수정 파일:
2. Scanner 구조:
3. Candidate 모델:
4. Quant Score 구조:
5. Market Regime 보정 적용 방식:
6. 제외/거절 사유:
7. Audit Event 연결:
8. 테스트 결과:
9. 금지 영역 변경 여부:
10. git diff 요약:
11. git status:
12. 커밋 여부: 미수행
```
