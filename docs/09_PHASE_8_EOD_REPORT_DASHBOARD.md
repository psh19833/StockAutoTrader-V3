# SAT3 개발계획서

> 목적: 이 문서는 Hermes Agent에게 한 번에 하나씩 전달하여 SAT 3.0을 안정적으로 개발하기 위한 단계별 작업 지시서다.  
> 원칙: 실전 자동매매 전용, 한국투자증권 Open API 단일 출처, 정량평가 중심, 로그 기반 운용 증거화, 작은 단위 개발.

---

# 09. Phase 8 - EOD Daily Performance Report + Dashboard Adapter

## 1. Phase 목적

이 Phase의 목표는 장 종료 후 오늘 하루의 자동매매 성과를 확인할 수 있는 EOD Daily Performance Report 기능을 만드는 것이다.

```text
핵심 질문:
- 오늘 얼마 벌었는가?
- 승률은 몇 %인가?
- 평균 수익률은 얼마인가?
- 어떤 전략이 잘 먹혔는가?
- 어떤 시장 상태에서 성과가 좋았는가?
- 정량평가 점수가 실제 수익과 연결됐는가?
- 리스크 거절은 적절했는가?
- API/서버 장애는 있었는가?
```

## 2. 작업 범위

생성/수정 권장 구조:

```text
backend/reports/
├─ eod_performance_report.py
├─ eod_report_builder.py
├─ eod_report_storage.py
├─ eod_telegram_formatter.py
└─ eod_dashboard_adapter.py

backend/tests/test_eod_performance_*.py
docs/sat3_eod_daily_performance_report.md
```

프론트엔드 작업은 이 Phase에서 **API adapter 또는 응답 schema 수준**까지만 권장한다.  
대시보드 UI 대규모 개편은 별도 후속 Phase로 분리해도 된다.

## 3. 금지 사항

```text
금지:
- KIS API 실패 시 수익률 추정
- 주문 성공을 거래 성과로 계산
- 미체결 주문을 체결로 계산
- 실현손익과 평가손익을 섞어 승률 계산
- fake fill 기반 리포트 생성
- fake balance 기반 리포트 생성
- KIS 외부 수익률 데이터 사용
```

## 4. EOD 생성 조건

EOD 리포트는 다음 조건이 충족된 뒤 생성한다.

```text
1. 오늘이 거래일
2. KIS 장운영정보 기준 정규장 종료 확인
3. 장후 체결/잔고 동기화 완료
4. 미체결 주문 상태 확인 완료
5. 실현손익 조회 완료
6. 기간별 손익 조회 완료
7. 포지션 스냅샷 저장 완료
8. 주문/체결/포지션 로그 마감 완료
```

주의:

```text
장 종료 시각이 되었다고 바로 리포트를 만들지 않는다.
KIS API 기준 최종 동기화 후 생성한다.
```

## 5. 필수 데이터 출처

```text
- KIS 주문체결조회
- KIS 잔고조회
- KIS 실현손익 조회
- KIS 기간별 손익 조회
- Audit Event Log
- Order Log
- Fill Log
- Position Log
- Market Regime Log
- Quant Evaluation Log
- Strategy Signal Log
- Risk Decision Log
- Scanner Log
- KIS API Log
```

## 6. DailyPerformanceReport 모델

```python
@dataclass(frozen=True)
class DailyPerformanceReport:
    trading_day: date

    account_summary: DailyAccountSummary
    trading_summary: DailyTradingSummary
    win_loss_metrics: WinLossMetrics

    symbol_performance: tuple[SymbolPerformance, ...]
    strategy_performance: tuple[StrategyPerformance, ...]
    market_regime_performance: tuple[MarketRegimePerformance, ...]
    score_bucket_performance: tuple[ScoreBucketPerformance, ...]
    scanner_performance: tuple[ScannerPerformance, ...]
    risk_rejection_summary: RiskRejectionSummary
    system_health_summary: SystemHealthSummary

    generated_at: datetime
    source_endpoints: tuple[str, ...]
    data_quality_warnings: tuple[str, ...]
```

## 7. 필수 리포트 항목

### 7.1 Daily Account Summary

```text
- 거래일
- 시작 예수금
- 종료 예수금
- 총 평가금액
- 총 실현손익
- 총 평가손익
- 총 손익
- 총 수익률
- 수수료
- 세금
- 순손익
- 순수익률
```

### 7.2 Daily Trading Summary

```text
- 총 주문 수
- 매수 주문 수
- 매도 주문 수
- 체결 수
- 취소 주문 수
- 실패 주문 수
- 미체결 주문 수
- 거래 종목 수
- 신규 진입 종목 수
- 청산 완료 종목 수
```

### 7.3 Win / Loss Metrics

```text
- 승리 거래 수
- 패배 거래 수
- 본전 거래 수
- 승률
- 평균 수익률
- 평균 손실률
- 평균 수익금액
- 평균 손실금액
- 최대 수익 거래
- 최대 손실 거래
- 손익비
- Profit Factor
```

계산 원칙:

```text
승률 = 수익 종료 거래 수 / 전체 종료 거래 수 * 100
미청산 보유 종목은 승률 계산에서 제외하거나 별도 표시
실현손익과 평가손익은 분리
```

### 7.4 Symbol Performance

```text
- 종목코드
- 종목명
- 매수 횟수
- 매도 횟수
- 평균 매수가
- 평균 매도가
- 보유 시간
- 실현손익
- 실현수익률
- 평가손익
- 평가수익률
- 수수료/세금
- 순손익
- 진입 전략
- 청산 사유
```

### 7.5 Strategy Performance

```text
- 전략명
- 신호 수
- 주문 승인 수
- 주문 거절 수
- 실제 진입 수
- 청산 완료 수
- 승률
- 평균 수익률
- 총 실현손익
- 최대 수익
- 최대 손실
- 평균 보유 시간
- Profit Factor
```

### 7.6 Market Regime Performance

```text
- Bull 상태 거래 수
- Neutral 상태 거래 수
- Bear 상태 거래 수
- 각 상태별 승률
- 각 상태별 평균 수익률
- 각 상태별 총 손익
- 시장 점수 보정 적용 거래 수
- Bear 상태 신규매수 차단 수
```

### 7.7 Score Bucket Performance

점수 구간:

```text
90점 이상
80~89점
70~79점
60~69점
60점 미만
```

각 구간별 항목:

```text
- 후보 수
- 신호 수
- 진입 수
- 승률
- 평균 수익률
- 총 손익
- 평균 보유 시간
```

### 7.8 Scanner Performance

```text
- 총 스캔 실행 횟수
- 총 수집 종목 수
- 중복 제거 후 후보 수
- 최종 평가 후보 수
- 전략 신호로 이어진 후보 수
- 실제 주문으로 이어진 후보 수
- 체결된 후보 수
- 수익 거래로 이어진 후보 수
- 스캔 타입별 성과
```

### 7.9 Risk Rejection Summary

```text
- 총 리스크 거절 수
- 거절 사유별 건수
- 세션 상태로 인한 거절
- 시장 상태로 인한 거절
- 일일 손실 제한 거절
- 중복 주문 거절
- 재진입 제한 거절
- 데이터 stale 거절
- API 조회 실패 거절
```

### 7.10 System Health Summary

```text
- API 호출 총 횟수
- API 실패 횟수
- endpoint별 실패 횟수
- 평균 latency
- 최대 latency
- WebSocket 끊김 횟수
- 재연결 횟수
- 예외 발생 횟수
- 주문 실패 횟수
- 데이터 누락 발생 횟수
- stale data 발생 횟수
```

## 8. 저장 방식

```text
1. DB 저장
- Dashboard 조회용
- 장기 성과 분석용

2. JSON 파일 저장
- data/reports/eod/YYYY-MM-DD.json

3. Telegram 요약 발송
- 장 종료 후 핵심 성과 확인용
```

기존 SAT2 EOD Telegram 구조가 있다면 재사용하되, SAT3 리포트 데이터를 받아 포맷팅하도록 확장한다.

## 9. Telegram 요약 예시

```text
[SAT 3.0 EOD 리포트]
거래일: 2026-05-04

시장상태:
- 최종 Regime: NEUTRAL
- 평균 Market Score: 58.4
- 신규매수 차단: 7건

성과:
- 실현손익: +42,500원
- 순손익: +38,900원
- 수익률: +0.78%
- 승률: 62.5%
- 거래: 8건 / 승 5 / 패 3

전략별:
- breakout: +31,000원 / 승률 75%
- pullback: -6,500원 / 승률 33%

리스크:
- 거절 12건
- 주요 사유: MARKET_REGIME_BLOCKED 5건, LATE_MARKET 4건

시스템:
- API 실패 2건
- 주문 실패 0건
- WebSocket 재연결 1회
```

## 10. Dashboard Adapter 요구사항

EOD 상세 화면에 필요한 API 응답 구조를 만든다.

```text
- 오늘 요약 카드
- 전략별 성과 테이블
- 종목별 성과 테이블
- Market Regime 성과
- 점수 구간별 성과
- 리스크 거절 요약
- 시스템 상태 요약
```

이 Phase에서는 백엔드 응답 schema와 adapter 중심으로 작업하고, UI는 최소 변경 또는 별도 Phase로 넘긴다.

## 11. 테스트 요구사항

테스트 파일 예시:

```text
backend/tests/test_eod_report_builder.py
backend/tests/test_eod_win_loss_metrics.py
backend/tests/test_eod_strategy_performance.py
backend/tests/test_eod_market_regime_performance.py
backend/tests/test_eod_report_storage.py
```

필수 테스트:

```text
1. 체결된 거래만 승률 계산에 포함
2. 미체결 주문은 성과 제외
3. 실현손익과 평가손익 분리
4. 전략별 성과 집계
5. Market Regime별 성과 집계
6. 점수 구간별 성과 집계
7. 리스크 거절 사유별 집계
8. API 실패/데이터 불일치 시 data_quality_warnings 생성
9. JSON 파일 저장
10. Telegram 요약 포맷 생성
11. EOD_REPORT_CREATED audit event 생성
```

## 12. 문서 산출물

```text
docs/sat3_eod_daily_performance_report.md
```

포함 내용:

```text
- EOD 생성 조건
- 필수 데이터 출처
- 리포트 데이터 모델
- 지표 계산 원칙
- 저장 방식
- Telegram 요약 형식
- Dashboard 요구사항
- 데이터 품질 경고 정책
```

## 13. 검증 명령

```bash
pytest backend/tests/test_eod_report_builder.py backend/tests/test_eod_win_loss_metrics.py backend/tests/test_eod_strategy_performance.py backend/tests/test_eod_market_regime_performance.py backend/tests/test_eod_report_storage.py
git diff -- backend/reports backend/tests docs/sat3_eod_daily_performance_report.md
git status --short
```

## 14. Hermes 보고 형식

```text
Phase 8 완료 보고

1. 생성/수정 파일:
2. EOD Report 데이터 모델:
3. 승률/수익률 계산 원칙:
4. 전략별/시장별/점수구간별 집계:
5. 저장 방식:
6. Telegram 요약:
7. Dashboard Adapter:
8. 테스트 결과:
9. 금지 영역 변경 여부:
10. git diff 요약:
11. git status:
12. 커밋 여부: 미수행
```
