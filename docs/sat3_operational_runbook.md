# SAT3 Operational Runbook

> SAT3 실전 운용 매뉴얼
> 마지막 수정: 2026-05-04
> 상태: Phase 1~9 Core 완료, N3~N5 KIS 연동 전

---

## 1. 시스템 개요

SAT3(StockAutoTrader V3)는 한국투자증권(KIS) Open API 기반 실전 자동매매 시스템이다.

### 핵심 원칙

1. **실전 계좌 전용** — 모의투자, paper trading 일체 금지
2. **KIS API 단일 출처** — 외부 크롤링, 임의 종목 리스트 금지
3. **KOSPI/KOSDAQ 보통주만** — ETF/ETN/ELW/REIT/SPAC/우선주 등 제외
4. **LIVE_TRADING_ENABLED=false 기본값** — 명시적 활성화 전까지 주문 차단
5. **주문 성공 ≠ 체결 성공** — 체결은 KIS 체결조회 기준으로만 확정
6. **모든 결정은 Audit Log로 증명** — SCAN → QUANT → STRATEGY → RISK → ORDER → FILL 추적

### 파이프라인

```
KIS API → Scanner → Quant → Strategy → Risk → LiveOrderGate → Order → Fill
               ↘ Audit Log (모든 단계 기록) ↙
                    Market Regime (시장 상태)
                    Session Guard (장 시간)
```

---

## 2. 시스템 아키텍처

```
backend/
├── kis/              # KIS API Gateway (인증, 호출, 오류처리)
├── session/          # 장 시간/휴장일 관리 (TradingCalendar, SessionGuard)
├── market_regime/    # 시장 상태 평가 (BULL/NEUTRAL/BEAR/UNKNOWN)
├── audit_logging/    # 감사 로그 (모든 결정 기록)
├── notifications/    # Telegram 알림 (Phase 3B)
├── scanner/          # 종목 스캐너 (4종: RAPID_SURGE, LIQUIDITY_MOMENTUM, BREAKOUT, PULLBACK_REBOUND)
├── quant/            # 정량 평가 엔진 (점수화, Decision: PASS/WATCH/REJECT)
├── strategy/         # 전략 신호 생성 (5종: 4 entry + FAST_EXIT)
├── risk/             # 리스크 엔진 (13종 거절 사유)
├── order/            # 주문 관리 (LiveOrderGate → SafeStubSubmitter)
├── portfolio/        # 포트폴리오 동기화 (Position, PnL)
├── reports/          # EOD 일일 성과 리포트
└── safety/           # Preflight, Release Gate, Config Validator
```

---

## 3. 일일 운용 절차

### 3.1 장 시작 전 (08:30 ~ 08:50)

```bash
# 1. 서버 상태 확인
cd /home/psh19/StockAutoTrader-V3
.venv/bin/python -c "from safety.preflight import run_preflight; \
  print(run_preflight(False, False, True, True, True, True).summary)"

# 2. Preflight Check
# - LIVE_TRADING_ENABLED: false (안전모드)
# - EMERGENCY_STOP: inactive
# - 모든 모듈 로드 확인

# 3. 오늘 거래일 확인
# - KIS API 휴장일 조회로 거래일 여부 확인
# - 휴장일이면 시스템 OFF
```

### 3.2 장 중 운용 (09:00 ~ 15:20)

```
감시 항목:
- Scanner 실행 상태 (scanner_engine.py)
- Quant 평가 결과 (candidate_score.py)
- Strategy 신호 발생 현황 (strategy_evaluator.py)
- Risk 거절 내역 (risk_engine.py)
- Telegram 알림 수신

주의:
- LIVE_TRADING_ENABLED=false 상태에서는 주문 제출되지 않음
- 실전 주문 전 반드시 LiveOrderGate 6단계 검증 통과 필요
- 장 마감 10분 전(15:20) 신규매수 금지
```

### 3.3 장 종료 후 (15:30 ~ 16:00)

```bash
# 1. EOD Report 생성
# - 체결 기준 성과 집계
# - 전략별/종목별/Regime별 성과
# - Risk 거절 요약
# - System Health

# 2. Audit Log 확인
# - 오늘 모든 이벤트 정상 기록 확인
# - 오류/실패 이벤트 검토

# 3. Telegram EOD 요약 수신 확인
```

---

## 4. Market Regime별 운용 정책

| Regime | 신규매수 | RAPID_SURGE | BREAKOUT | LIQUIDITY | PULLBACK |
|--------|---------|-------------|----------|-----------|----------|
| BULL | 허용 | 적극 | 적극 | 허용 | 허용 |
| NEUTRAL | 허용 | 고득점만 | 제한적 | 중심 | 중심 |
| BEAR | **차단** | 비활성 | 비활성 | 비활성 | 비활성 |
| UNKNOWN | **차단** | 비활성 | 비활성 | 비활성 | 비활성 |

---

## 5. Session State별 운용 정책

| State | 신규매수 | 스캔 | 청산 | EOD |
|-------|---------|------|------|-----|
| REGULAR_MARKET | ✅ | ✅ | ✅ | ❌ |
| CLOSED_HOLIDAY | ❌ | ❌ | ❌ | ❌ |
| CLOSED_BEFORE_MARKET | ❌ | ✅ | ❌ | ❌ |
| PRE_MARKET_AUCTION | ❌ | ✅ | ❌ | ❌ |
| LATE_MARKET | ❌ | ✅ | ✅ | ❌ |
| CLOSING_AUCTION | ❌ | ❌ | ✅ | ❌ |
| AFTER_MARKET | ❌ | ❌ | ❌ | ✅ |
| CLOSED_AFTER_MARKET | ❌ | ❌ | ❌ | ✅ |
| SESSION_STATE_UNKNOWN | ❌ | ❌ | ❌ | ❌ |

---

## 6. Risk Engine 거절 사유

| 코드 | 설명 | 대응 |
|------|------|------|
| LIVE_TRADING_DISABLED | 실전매매 비활성화 | 설정 확인 후 활성화 |
| EMERGENCY_STOP_BLOCKED | 비상정지 활성 | 비상정지 해제 절차 |
| MARKET_REGIME_BLOCKED | 시장 상태 차단 | BEAR/UNKNOWN 해제 대기 |
| SESSION_BLOCKED | 장 시간 외 | REGULAR_MARKET 대기 |
| DUPLICATE_ORDER_BLOCKED | 중복 주문 | 기존 주문 확인 |
| SYMBOL_EXPOSURE_BLOCKED | 동일 종목 보유 | 포지션 청산 후 재진입 |
| DAILY_LOSS_LIMIT_BLOCKED | 일일 손실 한도 초과 | 익일까지 대기 |
| POSITION_LIMIT_BLOCKED | 최대 보유 종목 초과 | 포지션 정리 |
| STALE_DATA_BLOCKED | 데이터 만료 | KIS API 재조회 |
| REENTRY_BLOCKED | 재진입 제한 | 제한시간 경과 대기 |
| DATA_QUALITY_BLOCKED | 데이터 품질 불량 | KIS API 정상화 대기 |

---

## 7. 로그 확인 방법

```bash
# Audit Event 확인 (InMemory)
cd /home/psh19/StockAutoTrader-V3
PYTHONPATH=./backend .venv/bin/python -c "
from audit_logging.audit_writer import get_writer
w = get_writer()
events = w.list_all()
for e in events[-20:]:
    print(f'[{e.timestamp}] {e.event_type} {e.symbol or \"\"} {e.severity}')
"

# 오늘 스캔 결과 확인
# (DB 연결 후)
```

---

## 8. 실전 운용 전 체크리스트 (N3~N5 완료 후)

- [ ] KIS API 인증 토큰 정상 발급
- [ ] 장운영정보 조회 정상
- [ ] 휴장일 조회 정상
- [ ] 현재가/호가 조회 정상
- [ ] 잔고/체결조회 정상
- [ ] LIVE_TRADING_ENABLED=false 확인
- [ ] Emergency Stop inactive 확인
- [ ] Telegram 알림 수신 확인
- [ ] EOD Report 정상 생성 확인
- [ ] Audit Log 정상 기록 확인
- [ ] 소액 테스트 주문 1회 (LIVE_TRADING_ENABLED=true)
- [ ] 체결 확인 후 주문-체결 불일치 없음 확인
- [ ] 손실 한도 내 운용 확인

---

## 9. 백업 및 복구

```bash
# 설정 백업
cp .env .env.backup.$(date +%Y%m%d)

# Audit Log 백업 (DB 연결 후)
# EOD Report 백업 (DB 연결 후)

# 복구
# .env 복원 후 서버 재시작
```

---

## 10. 연락처 및 에스컬레이션

- 시스템 담당자: (설정 필요)
- KIS API 고객센터: 1588-0037
- 비상 연락: (설정 필요)
